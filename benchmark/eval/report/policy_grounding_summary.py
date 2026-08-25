"""Aggregate the policy-grounding eval metrics across a Harbor sweep and surface CORPUS GAPS.

Reads each trial's ``verifier/reward.json`` (the ``policy_*`` keys) + ``verifier/grades_detail.json``
(per-citation verdicts, retrieval missed/extra, the 3-class outcome labels) + the bundled
``rubrics.json`` (scenario_id, gold docs). Prints markdown tables split by policy-ON / policy-OFF, and
a **corpus-gap** section:

  * per gold doc — how often it was cited when it was governing (low recall ⇒ the doc is hard to
    find or lacks the needed content);
  * per scenario — relevance label mix + whether grounding was systematically weak despite the corpus
    being present (a governing doc that doesn't actually contain the needed guidance = a corpus gap,
    not just an agent miss).

Fully offline, no creds — it only reads what the in-container judge already wrote (so the judge
creds must have been present during the run for the LLM-judged PR1/PC2 numbers to exist).

  python benchmark/eval/report/policy_grounding_summary.py \
      --on jobs/policy_on_XXXX --off jobs/policy_off_XXXX
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from clinicare_core.paths import bootstrap

HEALTHCARE = Path(__file__).resolve().parents[2]
TASKS_DIR = HEALTHCARE / "tasks"

bootstrap(__file__, "container_tests")
# _relevance_class is the single source of truth for the PR1 3-class rule. Keep this import on ONE
# line: isort wraps a long line into parenthesised form, and flake8 then reports E402 against the
# wrapped statement even though the noqa is present.
from policy_scoring import _relevance_class  # noqa: E402


def _find_rubrics(trial: Path, task_id: str) -> dict | None:
    for cand in (
        trial / "verifier" / "rubrics.json",
        TASKS_DIR / task_id / "tests" / "rubrics.json",
    ):
        if cand.is_file():
            try:
                return json.loads(cand.read_text())
            except ValueError:
                return None
    return None


def _load_json(p: Path) -> dict | None:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except ValueError:
        return None


def _collect(job_dirs: list[Path]) -> list[dict]:
    """One record per trial with a reward.json."""
    recs: list[dict] = []
    for jd in job_dirs:
        for trial in sorted(jd.glob("*__*")):
            reward = _load_json(trial / "verifier" / "reward.json")
            if reward is None:
                continue
            task_id = trial.name.rsplit("__", 1)[0]
            bundle = _find_rubrics(trial, task_id) or {}
            recs.append(
                {
                    "task_id": task_id,
                    # `case_id`: pre-rename spelling, still in bundles captured under jobs/.
                    "scenario_id": bundle.get("scenario_id")
                    or bundle.get("case_id")
                    or task_id.rsplit("-", 1)[0],
                    "gold_docs": list(bundle.get("policy_gold_docs") or []),
                    "reward": reward,
                    "detail": _load_json(trial / "verifier" / "grades_detail.json") or {},
                }
            )
    return recs


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def _fmt(x, pct=False):
    if x is None:
        return "-"
    return f"{x:.1f}" if pct else f"{x:.2f}"


def _outcome_labels(detail: dict) -> dict[str, str]:
    """{item_id: label} from grades_detail. judge.py NESTS the policy detail under ["policy"]
    (judge.py:704 `detail["policy"] = p_detail`); tolerate a flat layout too."""
    pol = detail.get("policy") if isinstance(detail.get("policy"), dict) else detail
    return {g.get("id"): g.get("label") for g in pol.get("outcome_graded", []) if g.get("id")}


def _pr1_class(rec: dict) -> str:
    """PR1 under the deterministic gold-doc-membership rule, RECOMPUTED from the trial's retrieval
    so it reflects the current rule even on runs scored before it landed. Delegates the 3-class
    bucketing to the scorer's own ``policy_scoring._relevance_class`` (single source of truth) fed
    the scorer's valid-cited set (``retrieval.cited`` = the same in-corpus + valid-span docs the
    scorer passes to retrieval_metrics), so the report can't drift from reward.json."""
    det = (
        rec["detail"].get("policy")
        if isinstance(rec["detail"].get("policy"), dict)
        else rec["detail"]
    )
    ret = det.get("retrieval") or {}
    cited = set(ret.get("cited") or [])
    gold = set(ret.get("gold") or rec.get("gold_docs") or [])
    return _relevance_class(cited, gold)


def _emit_on(recs: list[dict], out) -> None:
    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        by_scenario[r["scenario_id"]].append(r)

    out("## Policy-ON — per-scenario eval metrics\n")
    out(
        "scenario | n | outcome% | file_recall | fabricated/tot | resolve% | support% | PR1 relevance (F/P/N)"
        "\n† = deterministic-only (citation support not judged; run eval/metrics/policy_support.py"
        " --amend-reward). NOT comparable with a complete outcome — the mean is over fewer items."
    )
    out("---|---|---|---|---|---|---|---")
    tot_out, tot_rec, tot_det = [], [], []
    for scenario in sorted(by_scenario):
        rs = by_scenario[scenario]
        rw = [r["reward"] for r in rs]
        # Complete vs deterministic-only outcomes are separate measurements over different item
        # counts (see policy_scoring.py) — never averaged together.
        outcome = _mean([w.get("policy_outcome_pct") for w in rw])
        outcome_det = _mean([w.get("policy_outcome_pct_deterministic") for w in rw])
        recall = _mean([w.get("policy_file_recall") for w in rw])
        resolve = _mean([w.get("policy_citation_resolve_rate") for w in rw])
        support = _mean([w.get("policy_citation_support_rate") for w in rw])
        tot = sum(w.get("policy_citations_total", 0) for w in rw)
        fab = sum(w.get("policy_citations_fabricated", 0) for w in rw)
        rel = Counter(_pr1_class(r) for r in rs)
        rel_s = f"{rel.get('followed',0)}/{rel.get('partially_followed',0)}/{rel.get('did_not_follow',0)}"
        out(
            f"{scenario} | {len(rs)} | "
            f"{_fmt(outcome, pct=True) if outcome is not None else _fmt(outcome_det, pct=True) + '†'} | "
            f"{_fmt(recall)} | "
            f"{fab}/{tot} | {_fmt((resolve or 0)*100, pct=True) if resolve is not None else '-'} | "
            f"{_fmt((support or 0)*100, pct=True) if support is not None else '-'} | {rel_s}"
        )
        if outcome is not None:
            tot_out.append(outcome)
        if outcome_det is not None:
            tot_det.append(outcome_det)
        if recall is not None:
            tot_rec.append(recall)
    # Report the two populations separately and say when the complete one is empty — a bare "-"
    # reads as "no data" when the truth is "support was never judged; run policy_support.py".
    parts = [f"mean file-recall = {_fmt(_mean(tot_rec))}"]
    if tot_out:
        parts.insert(
            0,
            f"mean outcome% (complete) = {_fmt(_mean(tot_out), pct=True)} over {len(tot_out)} scenarios",
        )
    if tot_det:
        parts.insert(
            1 if tot_out else 0,
            f"mean outcome% (deterministic-only†) = {_fmt(_mean(tot_det), pct=True)} over {len(tot_det)} scenarios",
        )
    out("\n**Overall ON:** " + ", ".join(parts) + f" over {len(recs)} trials.")
    if tot_det and not tot_out:
        out(
            "  † NO scenario has a complete policy outcome: citation support was never judged. Run "
            "`eval/metrics/policy_support.py <job> --amend-reward` before reporting a policy number.\n"
        )
    else:
        out("")


def _emit_off(recs: list[dict], out) -> None:
    if not recs:
        return
    rw = [r["reward"] for r in recs]
    # No deterministic-only split here: the policy-OFF rubric is a single fixed abstention item
    # with no citation_support, so these trials always carry the complete `policy_outcome_pct`.
    outcome = _mean([w.get("policy_outcome_pct") for w in rw])
    stray = sum(1 for w in rw if w.get("policy_citations_total", 0) > 0)
    tot_cites = sum(w.get("policy_citations_total", 0) for w in rw)
    out("## Policy-OFF — abstention / ablation sanity\n")
    out(
        f"- {len(recs)} trials; mean outcome% = **{_fmt(outcome, pct=True)}** "
        "(100 = correctly emitted no citations)."
    )
    out(
        f"- {stray}/{len(recs)} trials emitted a `[policy: …]` citation despite no corpus "
        f"({tot_cites} total) — each is a parametric-recall fabrication.\n"
    )


def _emit_corpus_gaps(on_recs: list[dict], out) -> None:
    """Per gold doc: cite-rate when governing. Per scenario: weak-grounding flag."""
    # doc -> [was it cited? per trial where it's gold]
    doc_hit: dict[str, list[int]] = defaultdict(list)
    for r in on_recs:
        det = (
            r["detail"].get("policy")
            if isinstance(r["detail"].get("policy"), dict)
            else r["detail"]
        )
        ret = det.get("retrieval") or {}
        gold = set(r["gold_docs"]) or set(ret.get("gold") or [])
        cited = set(ret.get("cited") or [])
        missed = set(ret.get("missed") or [])
        for d in gold:
            hit = (
                1
                if (d in cited and d not in missed)
                else (0 if d in missed else (1 if d in cited else 0))
            )
            doc_hit[d].append(hit)

    out("## Corpus-gap read\n")
    out(
        "*Low cite-rate for a governing doc ⇒ it's hard to find or lacks the needed content. "
        "Cross-check against the relevance mix: a scenario that's mostly `partially`/`did_not_follow` "
        "while its gold docs are rarely cited is a candidate corpus gap, not just an agent miss.*\n"
    )
    out("### Gold docs by cite-rate (when governing)\n")
    out("gold doc | cite-rate | n(trials governing)")
    out("---|---|---")
    for d in sorted(doc_hit, key=lambda k: (_mean(doc_hit[k]) or 0)):
        out(f"{d} | {_fmt(_mean(doc_hit[d]))} | {len(doc_hit[d])}")

    # per-scenario weak-grounding flag. Under the team's rule (citing >=1 governing doc = grounded),
    # LOW RECALL IS NOT A FAILURE — a scenario that cites just one of several gold docs is still
    # `followed`. So flag genuine weakness: any trajectory that cited NO governing doc
    # (did_not_follow), or a scenario that mostly PADS with non-governing docs (>=50% partially).
    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for r in on_recs:
        by_scenario[r["scenario_id"]].append(r)
    flagged = []
    for scenario in sorted(by_scenario):
        rs = by_scenario[scenario]
        rel = Counter(_pr1_class(r) for r in rs)
        n = sum(rel.values()) or 1
        pct_partial = rel.get("partially_followed", 0) / n
        pct_none = rel.get("did_not_follow", 0) / n
        recall = _mean([r["reward"].get("policy_file_recall") for r in rs])
        if pct_none > 0 or pct_partial >= 0.5:
            flagged.append((scenario, pct_partial, pct_none, recall))
    if flagged:
        out("\n### Scenarios to inspect (weak / padded grounding)\n")
        out(
            "*Flagged when a scenario has any `did_not_follow` (cited no governing doc) or ≥50% "
            "`partially_followed` (grounded but also cited non-governing docs). Low file-recall is "
            "NOT flagged — citing ≥1 governing doc counts as grounded under the current rule.*\n"
        )
        out("scenario | %partially | %did_not_follow | mean file_recall")
        out("---|---|---|---")
        for scenario, pp, pn, recall in sorted(flagged, key=lambda x: (-x[1] - x[2], -x[2])):
            out(f"{scenario} | {pp*100:.0f}% | {pn*100:.0f}% | {_fmt(recall)}")
    else:
        out("\n*No scenario tripped the weak/padded-grounding flag.*")
    out("")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--on", action="append", default=[], type=Path, help="policy-ON job dir (repeatable)"
    )
    ap.add_argument(
        "--off", action="append", default=[], type=Path, help="policy-OFF job dir (repeatable)"
    )
    ap.add_argument("--out", default="", help="write the report here (default: stdout)")
    args = ap.parse_args()
    if not args.on and not args.off:
        sys.exit("give at least one --on or --off job dir")

    on_recs = _collect(args.on)
    off_recs = _collect(args.off)
    lines: list[str] = []

    def out(s=""):
        lines.append(s)

    out(
        f"# Policy-grounding eval summary\n\nON trials: {len(on_recs)} | OFF trials: {len(off_recs)}\n"
    )
    if on_recs:
        _emit_on(on_recs, out)
        _emit_corpus_gaps(on_recs, out)
    _emit_off(off_recs, out)

    report = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(report)
        print(f"wrote report -> {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
