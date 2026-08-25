"""Run every offline scorer over a finished job dir, in one command.

`harbor run` (or scripts/run_sweep.py) produces trials whose DETERMINISTIC outcome score is
already in `verifier/reward.json` — the in-container verifier needs no credentials. Everything
else is graded here, afterwards, from the persisted artifacts: the LLM-judged process rubric and
policy-citation support, the grounding metrics, and finally the report table.

    export JUDGE_BASE_URL=... JUDGE_API_KEY=...
    python benchmark/eval/grade.py jobs/<job>              # everything
    python benchmark/eval/grade.py jobs/<job> --dry-run    # coverage only, spends nothing
    python benchmark/eval/grade.py jobs/<job> --skip-llm   # deterministic stages only
    python benchmark/eval/grade.py 'jobs/cbench_sweep_*'   # globs, one report at the end

Stages run in dependency order and each is reported as ran / skipped (with a reason) / failed.
The exit code is non-zero if a stage that SHOULD have run failed, so this is safe in a pipeline.

TWO INPUT SHAPES, bridged here. `process`, `policy_support` and the report take a JOB dir and
find trials by globbing `<job>/*__*/`. The grounding metrics instead take `--traces <dir>` and
glob `<dir>/*/*/*`, i.e. a dir CONTAINING job dirs — so pointing them at `jobs/` would silently
score every job you have ever run. This module scopes them by building a temp dir holding one
symlink per requested job and passing that as `--traces`.

CONCURRENCY: every LLM stage — `process`, `policy_support`, `insight_grounding_llm` and
`insights_recall` — fans out across trials with `--concurrency` and caches its result per trial,
so a re-run costs only the trials that are missing or previously errored. Cached trials still
count toward the reported mean, so a resumed run reports the same job-wide number. `--force`
re-grades everything; `--limit` samples.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent  # benchmark/eval/
ROOT = HERE.parents[1]  # repo root
G = HERE / "metrics" / "grounding"
PY = sys.executable


class Stage:
    """One scorer invocation.

    `kind` decides how the job dir reaches it: "job" passes the dirs as positional args, "traces"
    passes the scoped symlink dir via --traces. `llm` marks stages that spend judge tokens, so
    --skip-llm / --dry-run can drop them. `needs` names a file that must exist for the stage to be
    runnable at all; when it is absent the stage is SKIPPED with that reason rather than failing.
    """

    def __init__(self, name, script, kind, llm, needs=None, extra=None, serial_note=""):
        self.name = name
        self.script = script
        self.kind = kind
        self.llm = llm
        self.needs = needs
        self.extra = extra or []
        self.serial_note = serial_note


GOLD = HERE / "gold"
STAGES = [
    # --- LLM, job-dir, parallel across trials, cached per trial -----------------------------
    Stage("process", HERE / "metrics" / "process.py", "job", llm=True),
    Stage("policy_support", HERE / "metrics" / "policy_support.py", "job", llm=True),
    # --- deterministic grounding ------------------------------------------------------------
    Stage(
        "evidence_retrieval_recall",
        G / "evidence_retrieval_recall.py",
        "traces",
        llm=False,
        needs=GOLD / "gold_sources.json",
    ),
    Stage("insight_grounding", G / "insight_grounding.py", "traces", llm=False),
    # policy_grounding is deterministic unless --support is passed; the LLM support check is
    # already covered by the policy_support stage above, so it is deliberately not passed here.
    Stage(
        "policy_grounding",
        G / "policy_grounding.py",
        "traces",
        llm=False,
        needs=GOLD / "policy_gold.json",
    ),
    # --- LLM grounding: serial over trials, NO cache ------------------------------------------
    Stage(
        "insight_grounding_llm",
        G / "insight_grounding_llm.py",
        "traces",
        llm=True,
    ),
    Stage(
        "insights_recall",
        G / "insights_recall.py",
        "traces",
        llm=True,
        needs=GOLD / "required_evidence.json",
    ),
]
# The report reads each trial's reward.json plus the process.json the first stage wrote, so it
# runs last and is never skipped.
REPORT = Stage("score_clinicare", HERE / "report" / "score_clinicare.py", "job", llm=False)


def scoped_traces(job_dirs: list[Path], tmp: Path) -> Path:
    """A dir holding one symlink per job, so `--traces` sees exactly these jobs and no others.

    Link names must be unique PER TARGET, not per basename. Two supplied jobs can share a
    basename (`runA/sweep1` and `runB/sweep1`), and keying on the basename alone would point one
    link at the first and drop the second from every trace-based stage — while the job-dir stages
    still counted both, yielding a report that looks complete over N jobs with grounding computed
    over fewer. Genuinely duplicate paths (overlapping globs) collapse to one link, which is
    correct; distinct targets get a `__2` suffix. The link name is what the grounding metrics
    print as the run label, so the plain basename is kept whenever it is unambiguous.
    """
    d = tmp / "traces"
    d.mkdir(parents=True, exist_ok=True)
    seen: set[Path] = set()
    for j in job_dirs:
        target = j.resolve()
        if target in seen:
            continue
        seen.add(target)
        name, n = target.name, 2
        while (d / name).exists():
            name, n = f"{target.name}__{n}", n + 1
        (d / name).symlink_to(target, target_is_directory=True)
    return d


# The ONE number worth reading per stage, and where it is persisted. Keyed by stage name ->
# (per-trial filename under verifier/, dotted key inside it, short label).
# A summary that only says "ok" forces you to scroll back through thousands of lines of per-trial
# output to find out what the stage actually produced -- so each stage reports its own mean here,
# recomputed from the files on disk rather than scraped from stdout.
# `reward.json` is the fallback source for the deterministic stages, which write no file of their own.
STAGE_METRIC: dict[str, tuple[str, str, str]] = {
    "process": ("process.json", "score.pct", "process%"),
    "policy_support": ("policy_support.json", "score.pct", "policy-support%"),
    "insight_grounding_llm": ("insight_grounding_llm.json", "grounding", "grounding"),
    "insights_recall": ("insights_recall.json", "insights_recall", "finding-recall"),
    "insight_grounding": ("reward.json", "grounding_id_precision", "id-precision"),
    "policy_grounding": ("reward.json", "policy_file_f1", "file-F1"),
}


def _dig(payload, dotted: str):
    cur = payload
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def stage_stats(name: str, job_dirs: list[Path]) -> dict | None:
    """Recompute a stage's headline mean from the per-trial files it persisted.

    Returns None when the stage has no registered metric (nothing to say) or wrote nothing.
    Judge failures are counted separately and EXCLUDED from the mean: averaging them in as 0
    would silently understate the metric, and they are retried on the next run anyway.
    """
    spec = STAGE_METRIC.get(name)
    if not spec:
        return None
    fname, key, label = spec
    vals: list[float] = []
    failed = missing = 0
    for jd in job_dirs:
        for trial in sorted(Path(jd).glob("*__*")):
            fp = trial / "verifier" / fname
            try:
                payload = json.loads(fp.read_text())
            except (OSError, ValueError):
                missing += 1
                continue
            if payload.get("error"):
                failed += 1
                continue
            v = _dig(payload, key)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals.append(float(v))
            else:
                missing += 1
    if not vals:
        return None
    return {
        "label": label,
        "mean": round(statistics.mean(vals), 3),
        "n": len(vals),
        "judge_failed": failed,
        "missing": missing,
    }


def fmt_stats(s: dict | None) -> str:
    if not s:
        return ""
    out = f"{s['label']} {s['mean']:.3f}  n={s['n']}"
    if s["judge_failed"]:
        out += f"  {s['judge_failed']} judge-failed"
    if s["missing"]:
        out += f"  {s['missing']} no-metric"
    return out


def run_stage(st: Stage, job_dirs: list[Path], traces: Path, args: argparse.Namespace) -> tuple:
    """(status, detail). status is one of ran / skipped / failed."""
    if args.stages and st.name not in args.stages:
        return "skipped", "not selected"
    if st.needs is not None and not st.needs.exists():
        return "skipped", f"missing {st.needs.relative_to(ROOT)}"
    if st.llm and args.skip_llm:
        return "skipped", "--skip-llm"

    cmd = [PY, str(st.script)]
    if st.kind == "job":
        cmd += [str(j) for j in job_dirs]
        # Only the two job-dir judges take these; the report takes neither.
        if st.llm:
            cmd += ["--concurrency", str(args.concurrency)]
            if args.judge_model:
                cmd += ["--judge-model", args.judge_model]
            if args.force:
                cmd.append("--force")
            if args.dry_run:
                cmd.append("--dry-run")
    else:
        cmd += ["--traces", str(traces)]
        if st.llm:
            if args.judge_model:
                cmd += ["--model", args.judge_model]
            if args.limit:
                cmd += ["--limit", str(args.limit)]
            # These two now fan out and cache per trial, same as process/policy_support.
            cmd += ["--concurrency", str(args.concurrency)]
            if args.force:
                cmd += ["--force"]
    cmd += st.extra

    if args.dry_run and st.kind == "traces" and st.llm:
        return "skipped", "--dry-run (no coverage mode on this scorer)"

    print(f"\n{'=' * 78}\n== {st.name}\n{'=' * 78}", flush=True)
    rc = subprocess.run(cmd, cwd=ROOT).returncode
    return ("ran", "") if rc == 0 else ("failed", f"exit {rc}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("jobs", nargs="+", help="job dirs or globs (e.g. jobs/cbench_sweep_*)")
    ap.add_argument(
        "--concurrency",
        type=int,
        default=12,
        help="parallel trials for every LLM stage (process, policy_support, and the two LLM grounding metrics)",
    )
    ap.add_argument("--judge-model", default="", help="override the judge model for LLM stages")
    ap.add_argument("--limit", type=int, default=0, help="cap trials for the LLM grounding stages")
    ap.add_argument("--force", action="store_true", help="re-grade trials that are already cached")
    ap.add_argument("--skip-llm", action="store_true", help="deterministic stages only, no spend")
    ap.add_argument("--dry-run", action="store_true", help="coverage only where supported")
    ap.add_argument("--stages", default="", help="comma-separated subset (default: all)")
    ap.add_argument("--csv", default="", help="passed to score_clinicare")
    args = ap.parse_args()
    args.stages = {s.strip() for s in args.stages.split(",") if s.strip()}

    unknown = args.stages - {s.name for s in STAGES} - {REPORT.name}
    if unknown:
        return _die(f"unknown --stages: {sorted(unknown)}")

    job_dirs = [Path(d) for p in args.jobs for d in sorted(glob.glob(p)) if os.path.isdir(d)]
    if not job_dirs:
        return _die(f"no job dirs matched {args.jobs}")
    for j in job_dirs:
        if not sorted(j.glob("*__*")):
            return _die(
                f"{j} holds no trial dirs (`<task>__<hash>/`) — pass the JOB dir, not a trial dir"
            )

    needs_judge = any(s.llm and (not args.stages or s.name in args.stages) for s in STAGES)
    if needs_judge and not (args.skip_llm or args.dry_run):
        if not (os.environ.get("JUDGE_BASE_URL") and os.environ.get("JUDGE_API_KEY")):
            return _die(
                "JUDGE_BASE_URL and JUDGE_API_KEY must be set for the LLM stages "
                "(or pass --skip-llm / --dry-run). See .env.template."
            )

    print(f"grading {len(job_dirs)} job(s): {', '.join(j.name for j in job_dirs)}")
    results = []
    tmp = Path(tempfile.mkdtemp(prefix="clinicare_grade_"))
    try:
        traces = scoped_traces(job_dirs, tmp)
        for st in STAGES:
            results.append((st.name, *run_stage(st, job_dirs, traces, args)))
        if not args.stages or REPORT.name in args.stages:
            REPORT.extra = ["--csv", args.csv] if args.csv else []
            results.append((REPORT.name, *run_stage(REPORT, job_dirs, traces, args)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'=' * 78}\n== summary\n{'=' * 78}")
    summary = {"jobs": [str(j) for j in job_dirs], "stages": {}}
    for name, status, detail in results:
        mark = {"ran": "ok", "skipped": "--", "failed": "FAIL"}[status]
        stats = stage_stats(name, job_dirs) if status == "ran" else None
        # The stage's own number first; `detail` (a skip/fail reason) only when there isn't one.
        print(f"  {mark:>4}  {name:26} {fmt_stats(stats) or detail}")
        summary["stages"][name] = {
            "status": status,
            "detail": detail,
            **({"metric": stats} if stats else {}),
        }
    # Persist it. A 750-trial grade prints thousands of per-trial lines, so the numbers are
    # unfindable by the time it finishes; this is the file to read afterwards.
    for jd in job_dirs:
        sp = Path(jd) / "grade_summary.json"
        try:
            sp.write_text(json.dumps(summary, indent=2) + "\n")
            print(f"\n  summary -> {sp}")
        except OSError as exc:
            print(f"  ! could not write {sp}: {exc}", file=sys.stderr)
    if not args.csv:
        print("  (add --csv <path> for the machine-readable score table)")
    failed = [n for n, s, _ in results if s == "failed"]
    if failed:
        print(f"\n{len(failed)} stage(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def _die(msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
