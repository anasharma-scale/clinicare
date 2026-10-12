"""Run ONE CliniCARE task with one system, into a caller-chosen job dir, and report the trial as JSON.

This is the stable execution command for wrappers (e.g. MedHELM): they pass a system tag and a task
id, and read one JSON line back. Everything about HOW a system runs (agent shim, model, web-off
flags, credential forwarding, preflights) comes from run_sweep.py, so a wrapper never duplicates
it and picks up CliniCARE changes for free.

    uv run python scripts/run_case.py --system codex-gpt56sol --task-id <task id> \\
        --jobs-dir jobs/medhelm --job-name <unique name>

.env is loaded here (real environment wins), so callers need not `set -a; source .env`.

Output contract — exit 0 and one JSON object on stdout whenever a trial dir exists:
    status          "ok"          the verifier ran and the agent raised nothing
                    "agent_error" the agent raised (e.g. timeout, non-zero exit) but the verifier ran
                    "dead"        unscored: no verifier result (setup/environment failure), or the
                                  verifier itself failed before scoring (clinicare_core.rewards)
    trial_dir       absolute path of <jobs-dir>/<job-name>/<task>__<suffix>/
    task_id         the task id (from the trial's task path, not its truncated dir name)
    model_name      config.agent.model_name of the trial      agent_name  config.agent.name
    agent_version   agent_info.version                         exception_type  or null
    graded          whether --grade left both judges' scores in reward.json (false without --grade,
                    and false when a judge skipped the trial, e.g. no report)
Exit 2 with a message on stderr when there is no trustworthy trial to report: a usage/preflight
error (nothing ran), harbor refusing the job (e.g. the job dir exists with different settings), a
trial whose result.json or reward.json cannot be parsed, or a finished trial in the job dir that
was built from a different version of the task.

Re-running with the same --job-name resumes: harbor keeps a finished trial and returns it without
re-running. That trial is reported only if its task is byte-identical to the current task dir
(harbor's task checksum); after a CliniCARE change or a task rebuild, use a new --job-name.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from dirhash import dirhash  # harbor's own task checksum (Task.checksum == dirhash(dir, sha256))

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_sweep
from clinicare_core import graded, load_env, verifier_failed

BASE = run_sweep.BASE
EXIT_USAGE = 2


def fail(msg: str) -> int:
    print(f"run_case: {msg}", file=sys.stderr)
    return EXIT_USAGE


class UnreadableTrial(Exception):
    """The trial's result.json or reward.json is not valid JSON, so nothing about it can be trusted."""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise UnreadableTrial(f"cannot read {path}: {exc}") from exc


def trial_report(job_dir: Path) -> dict | None:
    """The contract JSON for the single trial in `job_dir`, or None if harbor left no trial.

    Raises UnreadableTrial if the trial's result.json or reward.json cannot be parsed.
    """
    trials = [d for d in sorted(job_dir.glob("*__*")) if (d / "result.json").is_file()]
    if len(trials) != 1:
        return None
    trial = trials[0]
    result = _read_json(trial / "result.json")
    agent = result.get("config", {}).get("agent", {})
    exception = result.get("exception_info") or {}
    verified = (
        bool((result.get("verifier_result") or {}).get("rewards"))
        and (trial / "verifier" / "reward.json").is_file()
    )
    if verified:
        reward = _read_json(trial / "verifier" / "reward.json")
        verified = not verifier_failed(reward)  # its 0.0 is not a verdict
    status = "dead" if not verified else ("agent_error" if exception else "ok")
    task_path = (result.get("task_id") or {}).get("path") or ""
    return {
        "status": status,
        "trial_dir": str(trial.resolve()),
        "task_id": Path(task_path).name or result.get("task_name", "").split("/")[-1],
        "model_name": agent.get("model_name"),
        "agent_name": agent.get("name"),
        "agent_version": (result.get("agent_info") or {}).get("version"),
        "exception_type": exception.get("exception_type"),
        "task_checksum": result.get("task_checksum"),
    }


def log_tail(log: Path, lines: int = 5) -> str:
    try:
        return " | ".join(log.read_text().strip().splitlines()[-lines:])
    except OSError:
        return "(no log)"


def grade(job_dir: Path, trial_dir: Path, env: dict[str, str]) -> bool:
    """Add the LLM-judged scores (process_pct, policy_citation_support_rate) to reward.json.

    grade.py writes side files only; these two scripts are what amend reward.json. Both exit 0
    when they skip a trial (no report, no rubrics) without scoring it, so the result is whether
    the reward now carries both judges' keys, not just whether the scripts succeeded.
    """
    codes = [
        subprocess.run(
            [run_sweep.PY, f"benchmark/eval/metrics/{script}", str(job_dir), "--amend-reward"],
            env=env,
            stdout=sys.stderr,
            check=False,
        ).returncode
        for script in ("process.py", "policy_support.py")
    ]
    if any(code != 0 for code in codes):
        return False
    try:
        return graded(_read_json(trial_dir / "verifier" / "reward.json"))
    except UnreadableTrial:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--system", required=True, help="one System tag from run_sweep.py")
    ap.add_argument("--task-id", required=True, help="task dir name under --tasks")
    ap.add_argument("--jobs-dir", required=True, help="where harbor writes the job dir")
    ap.add_argument("--job-name", required=True, help="unique per (system, settings, task)")
    ap.add_argument("--tasks", default="benchmark/tasks", help="built task dir")
    ap.add_argument("--backend", choices=["docker", "modal"], default="docker")
    ap.add_argument("--effort", choices=["minimal", "low", "medium", "high", "xhigh"])
    ap.add_argument("--max-retries", type=int, default=None)
    ap.add_argument("--grade", action="store_true", help="run the LLM judges (needs JUDGE_*)")
    ap.add_argument("--dry-run", action="store_true", help="print the harbor command only")
    args = ap.parse_args()

    # run_sweep's helpers read os.environ, so merge .env into it (the real environment wins).
    run_sweep.os.environ.update(load_env(BASE))
    run_sweep.os.chdir(BASE)

    systems = [s for s in run_sweep.SYSTEMS if s.tag == args.system]
    if not systems:
        return fail(f"unknown system {args.system!r}; see SYSTEMS in scripts/run_sweep.py")
    system = systems[0]
    if not (BASE / args.tasks / args.task_id / "task.toml").is_file():
        return fail(f"task {args.task_id!r} not found under {args.tasks}")
    if not args.dry_run and run_sweep.preflight(systems, args.tasks, args.backend):
        return EXIT_USAGE
    env = run_sweep.child_env(args.backend)
    if env is None:
        return EXIT_USAGE

    jobs_dir = Path(args.jobs_dir).expanduser()
    jobs_dir = jobs_dir if jobs_dir.is_absolute() else BASE / jobs_dir
    cmd = run_sweep.build_cmd(
        system,
        args.tasks,
        k=1,
        n=1,
        backend=args.backend,
        effort=args.effort,
        max_retries=args.max_retries,
        dry_run=args.dry_run,
        job=args.job_name,
        extra=("-i", args.task_id, "-o", str(jobs_dir)),
    )
    if args.dry_run:
        shown = [c.split("=")[0] + "=***" if "_API_KEY=" in c else c for c in cmd]
        print(" ".join(shlex.quote(c) for c in shown))
        return 0

    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_dir = jobs_dir / args.job_name
    log_path = jobs_dir / f"{args.job_name}.log"
    with open(log_path, "a") as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, check=False)
    # harbor exits 0 whatever the trial's outcome, so a non-zero code means harbor itself refused,
    # e.g. an existing job dir with different settings. Any trial already in that dir is from the
    # old settings: report the refusal, never that trial.
    if rc.returncode != 0:
        return fail(f"harbor refused the job (exit {rc.returncode}): {log_tail(log_path)}")
    try:
        report = trial_report(job_dir)
    except UnreadableTrial as exc:
        return fail(str(exc))
    if report is None:
        return fail(f"harbor produced no trial; see {log_path}")
    # A resumed trial whose task has since changed (CliniCARE update, task rebuild in place) would
    # otherwise be served as a fresh result: harbor's resume compares settings, not task content.
    current = dirhash(BASE / args.tasks / args.task_id, "sha256")
    if report["task_checksum"] != current:
        return fail(
            f"the trial in {job_dir} was built from a different version of task {args.task_id} "
            "(task checksum differs); use a new --job-name, or delete that job dir to re-run"
        )
    report["graded"] = bool(
        args.grade and report["status"] != "dead" and grade(job_dir, Path(report["trial_dir"]), env)
    )
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
