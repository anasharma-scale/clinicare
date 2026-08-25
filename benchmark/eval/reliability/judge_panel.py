"""Phase 1 of the judge-panel study: re-grade a set of Harbor trajectories with a panel of
judge models x N replicates, emitting one JSONL row per (trajectory, judge_model, replicate)
with the per-criterion boolean grades.

Fully offline — reads each trial's ``verifier/report.md`` + ``agent/trajectory.json`` from
``jobs/`` and the bundled ``rubrics.json`` (from the trial's verifier dir if captured there,
else regenerated from the task dir). Reuses the real judge (``_template/tests/judge.py``) so
the grading is identical to in-trial scoring.

  export JUDGE_BASE_URL=... JUDGE_API_KEY=...
  python benchmark/eval/reliability/judge_panel.py \
      --job claude=jobs/healthcare_sample30_claudecode_sonnet5_XXXX \
      --job gpt=jobs/healthcare_sample30_codex_gpt55_XXXX \
      --judges openai/gpt-5.4,openai/gpt-5.5,claude-sonnet-4-6,claude-sonnet-5 \
      --reps 5 --out jobs/judge_panel.jsonl

`--job <agent_family>=<jobdir>` is repeatable; the family label (e.g. claude / gpt) is what
the family-bias analysis in judge_analysis.py keys on. Only the primary/outcome reward is
deterministic; this study is about the LLM-graded PROCESS rubric, so the outcome pass is not
re-run here.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from clinicare_core.paths import bootstrap

bootstrap(__file__, "eval")

HEALTHCARE = Path(__file__).resolve().parents[2]
JUDGE_PATH = HEALTHCARE / "_template" / "tests" / "judge.py"
TASKS_DIR = HEALTHCARE / "tasks"


def _load_judge():
    spec = importlib.util.spec_from_file_location("mimic_judge", JUDGE_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


J = _load_judge()

from core.judge_core import _build_reference, _grade  # noqa: E402


def _agent_work(report: str, trajectory: str) -> str:
    if report and trajectory:
        return f"### Agent report.md\n\n{report}\n\n### Agent tool-call trajectory\n\n{trajectory}"
    return f"### Agent report.md\n\n{report}" if report else ""


def _find_rubrics(trial: Path, task_id: str, rubrics_from: Path | None) -> tuple[Path | None, str]:
    """Locate the rubrics.json to grade against. Returns (path, source).

    Default source is the trial's own `verifier/rubrics.json` (what was actually scored in-trial).
    With `--rubrics-from <tasks_dir>` we instead prefer `<tasks_dir>/<task_id>/tests/rubrics.json`
    — used to RE-GRADE old trajectories against an EDITED rubric set (after tightening/stripping
    criteria), so the same fixed trajectories are scored with the new criteria. Falls back to the
    captured copy (flagged) if a task_id isn't present in that dir, so coverage stays visible."""
    if rubrics_from is not None:
        fresh = rubrics_from / task_id / "tests" / "rubrics.json"
        if fresh.is_file():
            return fresh, "rubrics-from"
        captured = trial / "verifier" / "rubrics.json"
        if captured.is_file():
            return captured, "captured-FALLBACK"
        return None, "none"
    captured = trial / "verifier" / "rubrics.json"
    if captured.is_file():
        return captured, "captured"
    regenerated = TASKS_DIR / task_id / "tests" / "rubrics.json"
    return (regenerated, "tasks") if regenerated.is_file() else (None, "none")


def _collect_trials(
    job_dirs: list[tuple[str, Path]], rubrics_from: Path | None = None
) -> list[dict]:
    """One record per gradeable trial (must have a report.md)."""
    trials: list[dict] = []
    for family, jd in job_dirs:
        for trial in sorted(jd.glob("*__*")):
            report = trial / "verifier" / "report.md"
            if not (trial.is_dir() and report.is_file()):
                continue  # no deliverable — degenerate, skip
            traj = next(
                (
                    trial / c
                    for c in ("agent/trajectory.json", "agent/output.txt", "agent/stdout.txt")
                    if (trial / c).is_file()
                ),
                None,
            )
            task_id = trial.name.rsplit("__", 1)[0]
            rub, rub_src = _find_rubrics(trial, task_id, rubrics_from)
            if rub is None:
                print(f"  skip {trial.name}: no rubrics.json found", file=sys.stderr)
                continue
            trials.append(
                {
                    "family": family,
                    "task_id": task_id,
                    "trial": trial.name,
                    "report": report,
                    "traj": traj,
                    "rub": rub,
                    "rub_src": rub_src,
                }
            )
    return trials


def _grade_one(t: dict, judge: str, rep: int, base_url: str, api_key: str) -> dict:
    # `judge` is a spec: "model" or "model@effort" (e.g. openai/gpt-5.5@xhigh). The full spec is
    # the display id (so gpt-5.5 and gpt-5.5@xhigh are distinct judges); effort is passed to the API.
    real_model, _, effort = judge.partition("@")
    bundle = json.loads(Path(t["rub"]).read_text())
    report = J._read_text(str(t["report"]))
    trajectory = J._read_trajectory(str(t["traj"])) if t["traj"] else ""
    work = _agent_work(report, trajectory)
    row = {
        "task_id": t["task_id"],
        "trial": t["trial"],
        # `case_id`: pre-rename spelling, still present in bundles captured under jobs/.
        "scenario_id": bundle.get("scenario_id") or bundle.get("case_id"),
        "agent_family": t["family"],
        "judge_model": judge,
        "rep": rep,
        "gt_label": (bundle.get("ground_truth_label") or "").upper(),
    }
    try:
        res = _grade(
            bundle.get("process_rubrics", []),
            bundle.get("prompt", ""),
            _build_reference(bundle),
            work,
            real_model,
            base_url,
            api_key,
            reasoning_effort=(effort or None),
        )
        row["grades"] = {
            g["id"]: (1 if str(g.get("grade", "")).lower() in ("met", "pass") else 0)
            for g in res["graded"]
        }
        row["process_pct"] = res["score"]["pct"]
        row["error"] = None
    except BaseException as exc:  # noqa: BLE001
        row["grades"] = {}
        row["process_pct"] = None
        row["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--job", action="append", required=True, metavar="FAMILY=JOBDIR", help="repeatable"
    )
    ap.add_argument(
        "--judges",
        required=True,
        help="comma-separated judge ids; each is 'model' or 'model@effort' "
        "(e.g. openai/gpt-5.5@xhigh — effort is passed as reasoning_effort and kept in the id)",
    )
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument(
        "--limit", type=int, default=0, help="cap trajectories per family (0=all; for smoke tests)"
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="append to --out and skip (trial, judge, rep) rows already graded OK in it "
        "(crash-safe restart; errored rows are re-run)",
    )
    ap.add_argument(
        "--rubrics-from",
        default=None,
        metavar="TASKS_DIR",
        help="re-grade against the CURRENT rubrics in this built-tasks dir "
        "(e.g. benchmark/tasks_answer) — <TASKS_DIR>/<task_id>/tests/rubrics.json — "
        "instead of each trial's captured copy. Use to score old trajectories with edited rubrics.",
    )
    args = ap.parse_args()

    base_url = os.environ.get("JUDGE_BASE_URL", "")
    api_key = os.environ.get("JUDGE_API_KEY", "")
    if not base_url or not api_key:
        sys.exit("ERROR: JUDGE_BASE_URL and JUDGE_API_KEY must be set")

    job_dirs = []
    for spec in args.job:
        fam, _, path = spec.partition("=")
        if not path:
            sys.exit(f"--job must be FAMILY=JOBDIR, got {spec!r}")
        job_dirs.append((fam, Path(path)))
    judges = [m.strip() for m in args.judges.split(",") if m.strip()]

    rubrics_from = Path(args.rubrics_from) if args.rubrics_from else None
    if rubrics_from is not None and not rubrics_from.is_dir():
        sys.exit(f"--rubrics-from dir not found: {rubrics_from}")
    trials = _collect_trials(job_dirs, rubrics_from=rubrics_from)
    if rubrics_from is not None:
        from collections import Counter

        src = Counter(t["rub_src"] for t in trials)
        print(f"rubrics source: {dict(src)}  (rubrics-from={rubrics_from})")
        if src.get("captured-FALLBACK"):
            print(
                f"  WARNING: {src['captured-FALLBACK']} trial(s) not found in {rubrics_from} — "
                "graded against their OLD captured rubric (excluded from a clean new-vs-old compare)",
                file=sys.stderr,
            )
    if args.limit:
        seen: dict[str, int] = {}
        capped = []
        for t in trials:
            if seen.get(t["family"], 0) < args.limit:
                capped.append(t)
                seen[t["family"]] = seen.get(t["family"], 0) + 1
        trials = capped
    fam_counts: dict[str, int] = {}
    for t in trials:
        fam_counts[t["family"]] = fam_counts.get(t["family"], 0) + 1
    print(f"trajectories: {len(trials)} ({fam_counts}) | judges: {judges} | reps: {args.reps}")
    total = len(trials) * len(judges) * args.reps

    # Resume: treat only OK-graded (trial, judge, rep) rows already in --out as done, so a
    # killed run continues where it left off; errored rows are re-graded. Rows are streamed to
    # disk (flush per grading) so an interrupt never loses completed work.
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done: set[tuple] = set()
    if args.resume and out_path.is_file():
        if rubrics_from is not None:
            print(
                "  WARNING: --resume with --rubrics-from — the resume key is (trial, judge, rep) and "
                "does NOT encode which rubric set was used. If this --out was produced against a "
                "DIFFERENT rubric set, its rows will be wrongly skipped (stale grades). Only resume "
                "onto an --out graded with the SAME --rubrics-from; otherwise start a fresh --out.",
                file=sys.stderr,
            )
        with open(out_path) as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001 — tolerate a torn final line
                    continue
                # .get() throughout: tolerate a row missing keys (foreign/old format) rather than
                # KeyError-crashing the whole resume load.
                judge_model, rep = r.get("judge_model"), r.get("rep")
                if (
                    r.get("error") is None
                    and r.get("grades")
                    and judge_model is not None
                    and rep is not None
                ):
                    done.add((r.get("trial"), judge_model, rep))
        print(f"resume: {len(done)} good gradings already in {args.out}; skipping those")

    work_items = [
        (t, m, r)
        for t in trials
        for m in judges
        for r in range(args.reps)
        if (t["trial"], m, r) not in done
    ]
    print(f"total gradings: {total} | to run now: {len(work_items)}")

    mode = "a" if (args.resume and out_path.is_file()) else "w"
    n_written = n_err = 0
    with open(out_path, mode) as fh, ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(_grade_one, t, m, r, base_url, api_key) for (t, m, r) in work_items]
        for i, f in enumerate(as_completed(futs), 1):
            row = f.result()
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            n_written += 1
            if row["error"]:
                n_err += 1
            if i % 50 == 0:
                print(f"  {i}/{len(work_items)} gradings done ({n_err} errors)", file=sys.stderr)
    print(f"wrote {n_written} rows -> {args.out}  ({n_err} grading errors)")


if __name__ == "__main__":
    main()
