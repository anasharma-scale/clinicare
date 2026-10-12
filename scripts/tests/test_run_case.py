"""Tests for run_case.py — the one-task execution contract that wrappers (MedHELM) depend on.

What a wrapper relies on, and therefore what must not drift silently:

  * `status` separates a scored trial ("ok"), a scored trial whose agent raised ("agent_error"),
    and an UNSCORED trial ("dead"). Harbor exits 0 in all three, so this field is the only signal;
    reporting a dead trial as scored would turn an infrastructure failure into a 0.0 answer.
  * `task_id` comes from the trial's task path, never its dir name: harbor truncates trial dir
    names to 32 characters, so the name is not a reliable task id.
  * run_case.py builds exactly run_sweep.py's command for the system, plus only `-i` and `-o`.
  * usage errors exit 2 before anything runs.
  * .env is read as the shell reads it: run_case.py loads it itself (load_env), and a trailing
    `# comment` kept in a value once crashed every codex trial (int('120   # codex (seconds)')).
  * a trial is reported only if harbor ran the job and the trial's task matches the current task
    dir: harbor's resume compares settings, not task content, so an old trial would otherwise be
    served as fresh after a CliniCARE change or a task rebuild.

Offline: fixtures are synthetic (placeholder ids), no harbor, no Docker, no credentials.

    python scripts/tests/test_run_case.py
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from dirhash import dirhash

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import run_case
import run_sweep
from clinicare_core import load_env

_fails: list[str] = []
# Longer than harbor's 32-char trial-name cap, to prove task_id is not read from the dir name.
LONG_ID = "placeholder-scenario-with-a-long-name-000001"


def check(label: str, cond: bool, detail: str = "") -> None:
    print(
        f"  {'ok  ' if cond else 'FAIL'}  {label}"
        + (f"   [{detail}]" if detail and not cond else "")
    )
    if not cond:
        _fails.append(label)


def make_trial(
    job: Path,
    task_id: str,
    *,
    rewards: bool,
    reward_file: bool,
    exc: str | None,
    checksum: str | None = None,
    reward: dict | None = None,
):
    trial = job / f"{task_id[:32].rstrip('_-')}__abcdefg"
    (trial / "verifier").mkdir(parents=True)
    result = {
        "task_name": f"mimic/{task_id}",
        "task_id": {"path": f"/somewhere/benchmark/tasks/{task_id}"},
        "config": {"agent": {"name": "pkg.mod:Agent", "model_name": "openai/placeholder"}},
        "agent_info": {"version": "1.2.3"},
        "verifier_result": {"rewards": {"reward": 1.0}} if rewards else None,
        "exception_info": {"exception_type": exc} if exc else None,
        "task_checksum": checksum,
    }
    (trial / "result.json").write_text(json.dumps(result))
    if reward_file:
        (trial / "verifier" / "reward.json").write_text(json.dumps(reward or {"score": 1.0}))
    return trial


def run_main_with_fake_harbor(
    *, harbor_rc: int, stale: bool, corrupt: str | None = None
) -> tuple[int, str]:
    """run_case.main() against a placeholder task, with preflight and harbor replaced by fakes."""
    task_id = "advanced-imaging-000001"
    with tempfile.TemporaryDirectory() as tmp:
        tasks = Path(tmp, "tasks")
        (tasks / task_id).mkdir(parents=True)
        (tasks / task_id / "task.toml").write_text("[task]\n")
        jobs = Path(tmp, "jobs")
        checksum = "stale" if stale else dirhash(tasks / task_id, "sha256")
        # The trial harbor would leave (or that an earlier run left) in the job dir.
        trial = make_trial(
            jobs / "jn", task_id, rewards=True, reward_file=True, exc=None, checksum=checksum
        )
        if corrupt:
            (trial / corrupt).write_text('{"score": 1.')

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, harbor_rc)

        argv = ["run_case.py", "--system", "codex-gpt56sol", "--task-id", task_id]
        argv += ["--tasks", str(tasks), "--jobs-dir", str(jobs), "--job-name", "jn"]
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(run_sweep, "preflight", return_value=0),
            mock.patch.object(run_sweep, "child_env", return_value={}),
            # build_cmd forwards the system's key; supply a placeholder so the test does not
            # depend on a developer's .env (a clean checkout or CI has none).
            mock.patch.dict(run_sweep.os.environ, {"OPENAI_API_KEY": "placeholder"}),
            mock.patch.object(run_case.subprocess, "run", side_effect=fake_run),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            rc = run_case.main()
        return rc, out.getvalue()


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        print("== 1. status classification ==")
        for name, kw, want in [
            ("ok", {"rewards": True, "reward_file": True, "exc": None}, "ok"),
            (
                "agent raised, verifier ran",
                {"rewards": True, "reward_file": True, "exc": "AgentTimeoutError"},
                "agent_error",
            ),
            (
                "no verifier result",
                {"rewards": False, "reward_file": False, "exc": "RuntimeError"},
                "dead",
            ),
            (
                "rewards but no reward.json",
                {"rewards": True, "reward_file": False, "exc": None},
                "dead",
            ),
            # The verifier's own failure paths still write score 0.0: unscored, not a wrong verdict.
            (
                "rubric bundle failed to load (judge.py)",
                {
                    "rewards": True,
                    "reward_file": True,
                    "exc": None,
                    "reward": {"score": 0.0, "judge_failed": 1, "rubrics_load_failed": 1},
                },
                "dead",
            ),
            (
                "judge failed to launch (test.sh)",
                {
                    "rewards": True,
                    "reward_file": True,
                    "exc": None,
                    "reward": {"score": 0.0, "judge_failed": 1, "judge_launch_failed": 1},
                },
                "dead",
            ),
            # ...whereas a missing report is a real 0, and judge_failed alone (process pass) is fine.
            (
                "agent wrote no report",
                {
                    "rewards": True,
                    "reward_file": True,
                    "exc": None,
                    "reward": {"score": 0.0, "report_present": 0, "report_chars": 0},
                },
                "ok",
            ),
            (
                "only the process judge failed",
                {
                    "rewards": True,
                    "reward_file": True,
                    "exc": None,
                    "reward": {"score": 1.0, "outcome_score": 1.0, "judge_failed": 1},
                },
                "ok",
            ),
        ]:
            job = root / name.replace(" ", "_").replace("/", "_")
            make_trial(job, "advanced-imaging-000001", **kw)
            got = run_case.trial_report(job)
            check(f"{name} -> {want}", got is not None and got["status"] == want, str(got))

        print("\n== 2. task id comes from the task path, not the truncated dir name ==")
        job = root / "long"
        trial = make_trial(job, LONG_ID, rewards=True, reward_file=True, exc=None)
        got = run_case.trial_report(job) or {}
        check("dir name really is truncated", not trial.name.startswith(LONG_ID))
        check("task_id is the full id", got.get("task_id") == LONG_ID, str(got.get("task_id")))
        check(
            "model/agent/version carried",
            (got.get("model_name"), got.get("agent_name"), got.get("agent_version"))
            == ("openai/placeholder", "pkg.mod:Agent", "1.2.3"),
        )

        print("\n== 3. no single trial -> None (caller reports 'harbor produced no trial') ==")
        check("empty job dir", run_case.trial_report(root / "missing") is None)
        job = root / "two"
        make_trial(job, "advanced-imaging-000001", rewards=True, reward_file=True, exc=None)
        make_trial(job, "advanced-imaging-000002", rewards=True, reward_file=True, exc=None)
        check("two trials", run_case.trial_report(job) is None)

    print("\n== 4. the command is run_sweep's, plus only -i/-o ==")
    system = next(s for s in run_sweep.SYSTEMS if s.tag == "codex-gpt56sol")
    base = run_sweep.build_cmd(system, "benchmark/tasks", 1, 1, "docker", dry_run=True)
    one = run_sweep.build_cmd(
        system,
        "benchmark/tasks",
        1,
        1,
        "docker",
        dry_run=True,
        job="jn",
        extra=("-i", "advanced-imaging-000001", "-o", "/tmp/jobs"),
    )
    jn_at = base.index("--job-name") + 1
    check("default job name unchanged", base[jn_at] == "cbench_sweep_codex-gpt56sol")
    check("job overrides the name", one[jn_at] == "jn")
    check(
        "only -i/-o added",
        one[:jn_at] + one[jn_at + 1 : len(base)] == base[:jn_at] + base[jn_at + 1 :]
        and one[len(base) :] == ["-i", "advanced-imaging-000001", "-o", "/tmp/jobs"],
    )

    print("\n== 5. usage errors exit 2 before running anything ==")
    for label, argv in [
        ("unknown system", ["--system", "no-such-system", "--task-id", "x"]),
        ("unknown task", ["--system", "codex-gpt56sol", "--task-id", "advanced-imaging-000001"]),
    ]:
        rc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "run_case.py"),
                *argv,
                "--jobs-dir",
                "/tmp/j",
                "--job-name",
                "n",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        check(f"{label} -> exit 2", rc == 2, f"exit {rc}")

    print("\n== 6. .env values match `set -a; source .env` ==")
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, ".env").write_text(
            "A_TRAILING=120   # comment\n"
            "B_PLAIN=value\n"
            'C_DOUBLE="has # inside"\n'
            "D_SINGLE='x y'\n"
            "E_HASH_NO_SPACE=abc#def\n"
            "F_REF=${B_PLAIN}/v1\n"
            'G_QUOTED_THEN_COMMENT="https://gw.example.com/v1"   # gateway\n'
            "H_EMPTY_THEN_COMMENT=   # leave blank\n"
            "I_SINGLE_THEN_COMMENT='abc'  # note\n"
        )
        env = load_env(Path(tmp))
        for key, want in [
            ("A_TRAILING", "120"),
            ("B_PLAIN", "value"),
            ("C_DOUBLE", "has # inside"),
            ("D_SINGLE", "x y"),
            ("E_HASH_NO_SPACE", "abc#def"),
            ("F_REF", "value/v1"),
            ("G_QUOTED_THEN_COMMENT", "https://gw.example.com/v1"),
            ("H_EMPTY_THEN_COMMENT", ""),
            ("I_SINGLE_THEN_COMMENT", "abc"),
        ]:
            check(f"{key} == {want!r}", env.get(key) == want, repr(env.get(key)))

    print("\n== 7. only a trustworthy trial is reported (main(), harbor faked) ==")
    for label, harbor_rc, stale, corrupt, want_rc in [
        ("fresh trial", 0, False, None, 0),
        ("harbor refused the job; an old trial is in the dir", 1, False, None, 2),
        ("resumed trial built from an older version of the task", 0, True, None, 2),
        ("malformed reward.json", 0, False, "verifier/reward.json", 2),
        ("malformed result.json", 0, False, "result.json", 2),
    ]:
        rc, out = run_main_with_fake_harbor(harbor_rc=harbor_rc, stale=stale, corrupt=corrupt)
        check(f"{label} -> exit {want_rc}", rc == want_rc, f"exit {rc}")
        check(f"{label}: JSON only on success", bool(out.strip()) == (want_rc == 0), repr(out))
        if want_rc == 0:
            report = json.loads(out)
            check(
                "fresh trial: status ok, not graded",
                (report.get("status"), report.get("graded")) == ("ok", False),
            )

    print()
    if _fails:
        print(f"{len(_fails)} FAILURE(S): " + "; ".join(_fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
