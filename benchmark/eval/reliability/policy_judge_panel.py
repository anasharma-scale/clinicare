"""Phase 1 of the POLICY judge-panel study: re-grade a set of Harbor trajectories' POLICY
outcome rubric with a panel of judge models x N replicates, emitting one JSONL row per
(trajectory, judge_model, replicate) with the per-item **3-class** grade (score + label).

The policy analogue of ``judge_panel.py`` (which studies the boolean process rubric). It differs
in three ways, all forced by the policy rubric's shape:
  * it reads ``policy_rubrics`` from the bundle (not ``process_rubrics``);
  * it grades via ``policy_scoring.grade_policy_outcome`` (not ``judge._grade``), passing the
    judge model as EXPLICIT creds — so a panel of models runs concurrently without racing a
    shared ``JUDGE_MODEL`` env var;
  * each grade is **3-class** — ``followed`` / ``partially_followed`` / ``did_not_follow`` →
    ``1.0`` / ``0.5`` / ``0.0`` (an item with nothing to check is ``not_applicable`` → score
    ``None``, excluded downstream), not boolean met/not-met.

Only the **policy-ON** condition is graded: policy-OFF is a deterministic abstention check with
no LLM in the loop, so there is no judge variance to characterize. Trajectories whose bundle has
``policy_expected = false`` (or no ``policy_rubrics``) are skipped.

Fully offline over ``jobs/`` — reads each trial's ``verifier/report.md`` + the bundled
``rubrics.json`` (from the trial's verifier dir if captured, else the task dir), and resolves
policy citations against ``--corpus`` (the same corpus staged into the container, so the
existence/support grades match the in-trial scorer).

  # judge creds from the env (JUDGE_*):
  export JUDGE_BASE_URL=... JUDGE_API_KEY=...     # or source .env
  python benchmark/eval/reliability/policy_judge_panel.py \
      --job claude=jobs/policy_on_XXXX \
      --judges "openai/gpt-5.5,openai/gpt-4o,openai/gpt-5.4-mini" \
      --reps 3 --out jobs/policy_judge_panel.jsonl

``--job <agent_family>=<jobdir>`` is repeatable; the family label keys the family-bias analysis
in policy_judge_analysis.py. A judge id is ``model`` or ``model@effort`` (e.g.
``openai/gpt-5.5@xhigh`` — effort is passed as reasoning_effort and kept in the id,
so it is a distinct judge from plain gpt-5.5).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from clinicare_core.paths import bootstrap

HEALTHCARE = Path(__file__).resolve().parents[2]

bootstrap(__file__, "container_tests")
import policy_scoring as P  # noqa: E402

# The corpus is assembled locally, not repo content (benchmark/corpus/README.md);
# CLINICARE_CORPUS_DIR points at the directory acquire_corpus.py built.
DEFAULT_CORPUS = Path(os.environ.get("CLINICARE_CORPUS_DIR") or (HEALTHCARE / "corpus"))
TASKS_DIR = HEALTHCARE / "tasks"


def _find_rubrics(trial: Path, task_id: str) -> Path | None:
    """The bundle carrying policy_rubrics/policy_gold_docs/policy_expected: prefer the copy
    captured in the trial's verifier dir, fall back to the (rebuilt) task dir."""
    captured = trial / "verifier" / "rubrics.json"
    if captured.is_file():
        return captured
    regen = TASKS_DIR / task_id / "tests" / "rubrics.json"
    return regen if regen.is_file() else None


def _collect_trials(job_dirs: list[tuple[str, Path]]) -> list[dict]:
    """One record per gradeable POLICY-ON trajectory (report.md present, policy_expected, and an
    authored policy rubric to grade)."""
    trials: list[dict] = []
    for family, jd in job_dirs:
        for trial in sorted(jd.glob("*__*")):
            report = trial / "verifier" / "report.md"
            if not (trial.is_dir() and report.is_file()):
                continue  # no deliverable — degenerate, skip
            task_id = trial.name.rsplit("__", 1)[0]
            rub = _find_rubrics(trial, task_id)
            if rub is None:
                print(f"  skip {trial.name}: no rubrics.json found", file=sys.stderr)
                continue
            bundle = json.loads(Path(rub).read_text())
            if not bundle.get("policy_expected"):
                # policy-off / no gold ⇒ deterministic abstention check, no judge variance to study
                continue
            if not bundle.get("policy_rubrics"):
                print(
                    f"  skip {trial.name}: policy_expected but no policy_rubrics", file=sys.stderr
                )
                continue
            trials.append(
                {"family": family, "task_id": task_id, "report": report, "bundle": bundle}
            )
    return trials


def _grade_one(
    t: dict, judge: str, rep: int, base_url: str, api_key: str, corpus_dir: Path
) -> dict:
    # `judge` is a spec: "model" or "model@effort". The full spec is the display id (so gpt-4o and
    # gpt-4o@high are distinct judges); the effort is passed to the API as reasoning_effort.
    real_model, _, effort = judge.partition("@")
    b = t["bundle"]
    report = Path(t["report"]).read_text(errors="replace")
    rubrics = b.get("policy_rubrics") or []
    gold = set(b.get("policy_gold_docs") or [])
    creds = {
        "model": real_model,
        "base_url": base_url,
        "api_key": api_key,
        "reasoning_effort": (effort or None),
    }
    kind_by_id = {r.get("id"): r.get("kind", "relevance") for r in rubrics}
    weight_by_id = {r.get("id"): r.get("weight", "+1") for r in rubrics}
    row = {
        "task_id": t["task_id"],
        # `case_id`: pre-rename spelling, still present in bundles captured under jobs/.
        "scenario_id": b.get("scenario_id") or b.get("case_id"),
        "agent_family": t["family"],
        "judge_model": judge,
        "rep": rep,
        "policy_expected": True,
        "gt_label": (b.get("ground_truth_label") or "").upper(),
    }
    try:
        cites = P.parse_citations(report)
        resolved = [P.resolve_citation(c, corpus_dir) for c in cites]
        # A citation_support item is graded FROM the LLM support results; compute them (per
        # resolved-valid citation) so the support item isn't scored not-applicable.
        support_results: list[dict | None] | None = None
        if any(r.get("kind") == "citation_support" for r in rubrics):
            support_results = [
                (
                    P.judge_support(c.sentence, r["cited_text"], creds)
                    if (r["in_corpus"] and r["span_valid"])
                    else None
                )
                for c, r in zip(cites, resolved)
            ]
        outcome = P.grade_policy_outcome(
            True,
            cites,
            resolved,
            gold,
            report,
            rubrics,
            b.get("prompt", ""),
            creds,
            support_results=support_results,
        )
        if outcome is None:
            raise RuntimeError("grade_policy_outcome returned None (missing rubric or creds)")
        graded = outcome["graded"]
        # score ∈ {1.0, 0.5, 0.0, None(n/a)}; label ∈ 3-class ∪ {not_applicable}.
        row["grades"] = {g["id"]: g["score"] for g in graded}
        row["labels"] = {g["id"]: g["label"] for g in graded}
        row["kinds"] = {g["id"]: kind_by_id.get(g["id"]) for g in graded}
        row["weights"] = {g["id"]: weight_by_id.get(g["id"]) for g in graded}
        row["outcome_pct"] = outcome["score"]["pct"]
        row["n_citations"] = len(cites)
        row["error"] = None
    except BaseException as exc:  # noqa: BLE001
        row["grades"] = {}
        row["labels"] = {}
        row["outcome_pct"] = None
        row["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    return row


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--job", action="append", required=True, metavar="FAMILY=JOBDIR", help="repeatable"
    )
    ap.add_argument(
        "--judges",
        required=True,
        help="comma-separated judge ids; each is 'model' or 'model@effort' "
        "(effort → reasoning_effort, kept in the id)",
    )
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS,
        help=f"policy corpus dir (default {DEFAULT_CORPUS})",
    )
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument(
        "--limit", type=int, default=0, help="cap trajectories per family (0=all; for smoke tests)"
    )
    args = ap.parse_args()

    # Judge creds from JUDGE_BASE_URL / JUDGE_API_KEY — mirrors policy_scoring._creds_from_env
    # so the panel and the in-container scorer read the same env (e.g. a sourced .env).
    base_url = os.environ.get("JUDGE_BASE_URL") or os.environ.get("JUDGE_BASE_URL") or ""
    api_key = os.environ.get("JUDGE_API_KEY") or os.environ.get("JUDGE_API_KEY") or ""
    if not base_url or not api_key:
        sys.exit("ERROR: set JUDGE_BASE_URL/JUDGE_API_KEY (or JUDGE_BASE_URL/JUDGE_API_KEY)")
    if not args.corpus.is_dir():
        sys.exit(f"ERROR: corpus dir not found: {args.corpus}")

    job_dirs = []
    for spec in args.job:
        fam, _, path = spec.partition("=")
        if not path:
            sys.exit(f"--job must be FAMILY=JOBDIR, got {spec!r}")
        job_dirs.append((fam, Path(path)))
    judges = [m.strip() for m in args.judges.split(",") if m.strip()]

    trials = _collect_trials(job_dirs)
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
    print(
        f"policy-ON trajectories: {len(trials)} ({fam_counts}) | judges: {judges} | reps: {args.reps}"
    )
    print(f"total gradings: {len(trials) * len(judges) * args.reps}")
    if not trials:
        sys.exit(
            "no policy-ON trajectories found (need report.md + policy_expected + policy_rubrics)"
        )

    work_items = [(t, m, r) for t in trials for m in judges for r in range(args.reps)]
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [
            ex.submit(_grade_one, t, m, r, base_url, api_key, args.corpus)
            for (t, m, r) in work_items
        ]
        for i, f in enumerate(futs, 1):
            rows.append(f.result())
            if i % 25 == 0:
                print(f"  {i}/{len(futs)} gradings done", file=sys.stderr)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    n_err = sum(1 for r in rows if r["error"])
    print(f"wrote {len(rows)} rows -> {args.out}  ({n_err} grading errors)")


if __name__ == "__main__":
    main()
