"""policy_grounding — document precision and citation support, offline.

Scores an agent's policy citations in report.md: the policy analogue of the patient-evidence
metrics, but over the guideline corpus and the ``[policy: <doc> L<a>-L<b>]`` citations in
``report.md`` rather than MIMIC tables. Two axes, scored SEPARATELY from patient-evidence
grounding and under BOTH conditions:

  * Policy citation correctness (evals): corpus-existence, span validity, file-level P/R/F1
    vs the expert gold docs, and — with ``--support`` — an LLM check that each cited passage
    factually backs its claim.
  * Policy relevance / outcome rubric (deterministic, condition-aware): did the agent cite the
    governing docs when a corpus was available (policy-on), or emit NO citations when it was
    not (policy-off).

All scoring lives in the shared core ``_template/tests/policy_scoring.py`` (imported below), so
this CLI and the in-container Harbor verifier compute identical numbers.

  cd <repo root>
  python benchmark/eval/metrics/grounding/policy_grounding.py --traces <trace dir>
  # add the optional LLM support check (needs JUDGE_BASE_URL / JUDGE_API_KEY / JUDGE_MODEL):
  python .../metrics/policy_grounding.py --support
  # force the condition when the run name does not encode it:
  python .../metrics/policy_grounding.py --condition off
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from clinicare_core.paths import bootstrap

HERE = Path(__file__).resolve().parent
HEALTHCARE = HERE.parents[2]

bootstrap(__file__, "container_tests")
from policy_scoring import score_policy_grounding  # noqa: E402

_OFF_HINT = re.compile(
    r"no[-_]?policy|policy[-_]?off|policyoff|nopolicy|_off\b|-off\b", re.IGNORECASE
)


def load_gold(path: Path) -> dict[str, set[str]]:
    """{scenario_id: set(policy_docs)} from policy_gold.json."""
    data = json.loads(Path(path).read_text())
    return {g["scenario_id"]: set(g.get("policy_docs", [])) for g in data}


def match_scenario(slug: str, gold: dict[str, set[str]]) -> str | None:
    """Trace scenario dir == scenario_id (exact); fall back to token overlap for safety."""
    if slug in gold:
        return slug
    toks = set(slug.lower().split("-"))
    best, best_n = None, 0
    for cid in gold:
        n = len(toks & set(cid.lower().split("-")))
        if n > best_n:
            best, best_n = cid, n
    return best


def infer_expected(condition: str, run: str, slug: str, scenario_gold: set[str]) -> bool:
    """policy_expected: on/off forced, else inferred from the run/scenario name; a scenario with no
    gold docs is never 'expected' (nothing governing to cite)."""
    if condition == "on":
        return bool(scenario_gold)
    if condition == "off":
        return False
    is_off = bool(_OFF_HINT.search(run) or _OFF_HINT.search(slug))
    return (not is_off) and bool(scenario_gold)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--traces", type=Path, default=HERE.parents[1] / "traces")
    ap.add_argument("--gold", type=Path, default=HERE.parents[1] / "gold" / "policy_gold.json")
    ap.add_argument(
        "--corpus",
        type=Path,
        # Separate download, not repo content — see benchmark/corpus/README.md.
        default=Path(os.environ.get("CLINICARE_CORPUS_DIR") or (HEALTHCARE / "corpus")),
    )
    ap.add_argument("--condition", choices=["auto", "on", "off"], default="auto")
    ap.add_argument("--support", action="store_true", help="run the optional LLM support check")
    ap.add_argument("--verbose", action="store_true", help="print per-citation detail")
    args = ap.parse_args()

    gold = load_gold(args.gold)
    reports = sorted(args.traces.glob("*/*/*/report.md"))
    if not reports:
        sys.exit(f"no report.md under {args.traces}")

    # The scorer reads JUDGE_* creds from the environment; the LLM support check and
    # relevance rubric run only if those are set. --support just forces the support check on.
    # Mirror _creds_from_env's conjunction: BOTH a base URL and an API key must be present, else
    # --support would pass this guard then silently degrade inside the scorer.
    have_base = os.environ.get("JUDGE_BASE_URL")
    have_key = os.environ.get("JUDGE_API_KEY")
    if args.support and not (have_base and have_key):
        sys.exit("--support needs JUDGE_BASE_URL and JUDGE_API_KEY in the environment")

    rows = []
    for rp in reports:
        run, slug = rp.parts[-4], rp.parts[-3]
        cid = match_scenario(slug, gold)
        if cid is None:
            print(f"  ! {slug}: no gold match", file=sys.stderr)
            continue
        expected = infer_expected(args.condition, run, slug, gold[cid])
        reward, detail = score_policy_grounding(
            rp.read_text(errors="replace"),
            args.corpus,
            gold[cid],
            expected,
            run_support=(True if args.support else None),
        )
        rows.append((run, slug, expected, reward, detail))

    hdr = f"{'run':26s} {'scenario':20s} {'exp':>3s} {'cites':>5s} {'valid':>5s} {'fab':>4s} {'recall':>6s} {'out%':>5s}"
    if args.support:
        hdr += f" {'supp':>5s}"
    print(hdr)
    on_out, off_out, recalls = [], [], []
    for run, slug, expected, rw, det in rows:
        rec = rw.get("policy_file_recall")
        rec_s = f"{rec:.2f}" if rec is not None else "   -"
        supp = rw.get("policy_citation_support_rate")
        # policy_outcome_pct is absent when the outcome wasn't graded (policy-ON w/o judge creds,
        # or scorer error) — print "-" and skip it in the mean rather than KeyError-ing.
        out_pct = rw.get("policy_outcome_pct")
        out_s = f"{out_pct:5.0f}" if out_pct is not None else "    -"
        line = (
            f"  {run[:24]:24s} {slug:20s} {('on' if expected else 'off'):>3s} "
            f"{rw['policy_citations_total']:>5d} {rw['policy_citations_in_corpus']:>5d} "
            f"{rw['policy_citations_fabricated']:>4d} {rec_s:>6s} {out_s:>5s}"
        )
        if args.support:
            line += f" {(f'{supp:.2f}' if supp is not None else '   -'):>5s}"
        print(line)
        if out_pct is not None:
            (on_out if expected else off_out).append(out_pct)
        if expected and rec is not None:
            recalls.append(rec)
        if args.verbose:
            for c in det["citations"]:
                flag = "ok" if (c["in_corpus"] and c["span_valid"]) else "FABRICATED"
                print(f"      [{flag}] {c['raw']}  ← {c['sentence'][:80]}")

    print()
    if recalls:
        print(
            f"policy-on  mean file-recall over {len(recalls)} trials: {sum(recalls)/len(recalls):.3f}"
        )
    if on_out:
        print(
            f"policy-on  mean outcome pct over {len(on_out)} trials: {sum(on_out)/len(on_out):.1f}"
        )
    if off_out:
        print(
            f"policy-off mean outcome pct over {len(off_out)} trials: {sum(off_out)/len(off_out):.1f}"
        )

    # Found inputs but scored none => every one failed to join (missing report, no gold match).
    # Exit non-zero rather than printing an empty table and exiting 0: a silent 0/N reads as
    # "nothing to score" when it means the join is broken.
    if not rows:
        print(
            f"\n❌ scored 0 of {len(reports)} report(s) — nothing joined",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
