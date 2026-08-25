#!/usr/bin/env python3
"""Smoke tests for the policy-grounding scorer (_template/tests/policy_scoring.py).

Deterministic checks need no creds/network. The LLM policy-relevance check runs only when judge
creds are present (JUDGE_BASE_URL / JUDGE_API_KEY / JUDGE_MODEL), else it SKIPs — so this is safe
to run offline and more thorough on-VPN.

  cd <repo root>
  uv run python benchmark/eval/tests/test_policy_grounding.py
  # with the LLM relevance check too (needs VPN + a model the key allows):
  JUDGE_BASE_URL=$JUDGE_BASE_URL JUDGE_API_KEY=$JUDGE_API_KEY \
    JUDGE_MODEL=anthropic/claude-sonnet-4-6 \
    uv run python benchmark/eval/tests/test_policy_grounding.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from clinicare_core.paths import bootstrap

bootstrap(__file__, "container_tests")
import policy_scoring as P  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(
        f"  {'ok  ' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not cond else "")
    )
    if not cond:
        FAILS.append(name)


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "gov-a.md").write_text(
        "---\ntitle: a\n---\n\n# A\nAntibiotics within 3 hours of triage.\nMore.\n"
    )
    (tmp / "gov-b.md").write_text(
        "---\ntitle: b\n---\n\n# B\nCultures before antibiotics.\nMore.\n"
    )

    print("== 1. citation parsing ==")
    cites = P.parse_citations(
        "Claim one [policy: gov-a.md L6-L7]. Claim two [policy: ghost.md L1-L2]."
    )
    check("two citations parsed", len(cites) == 2)
    check(
        "doc + line span captured",
        cites[0].doc == "gov-a.md" and (cites[0].line_start, cites[0].line_end) == (6, 7),
    )

    print("== 2. corpus resolution ==")
    r0 = P.resolve_citation(cites[0], tmp)
    r1 = P.resolve_citation(cites[1], tmp)
    bad_span = P.resolve_citation(P.parse_citations("[policy: gov-a.md L900-L901]")[0], tmp)
    check("real doc + valid span resolves", r0["in_corpus"] and r0["span_valid"])
    check("nonexistent doc flagged", not r1["in_corpus"])
    check(
        "out-of-range span flagged", r1 and (not bad_span["span_valid"]) and bad_span["in_corpus"]
    )

    print("== 3. file-level retrieval metrics ==")
    m = P.retrieval_metrics({"gov-a.md", "gov-b.md"}, {"gov-a.md"})
    check("recall = 0.5", m["recall"] == 0.5, str(m["recall"]))
    check("precision = 1.0", m["precision"] == 1.0, str(m["precision"]))

    print("== 4. policy-OFF outcome (deterministic 3-class abstention) ==")
    off_clean, _ = P.score_policy_grounding("Answer: No.\n", tmp, set(), policy_expected=False)
    check("clean abstention → followed → pct 100", off_clean["policy_outcome_pct"] == 100.0)
    off_bad, _ = P.score_policy_grounding(
        "Answer: Yes [policy: gov-a.md L6-L7].\n", tmp, set(), policy_expected=False
    )
    check(
        "stray citation → did_not_follow → pct 0",
        off_bad["policy_outcome_pct"] == 0.0,
        str(off_bad["policy_outcome_pct"]),
    )

    print("== 5. policy reported as a SEPARATE axis (not blended into score) ==")
    # judge.py does not fold policy into the primary `score`: the scorer emits
    # policy_outcome_pct as its own reward key and never sets `score` (that stays the outcome-label
    # match, owned by judge.py).
    check("policy_outcome_pct emitted as its own key", "policy_outcome_pct" in off_clean)
    check("clean abstention outcome = 100", off_clean["policy_outcome_pct"] == 100.0)
    check("scorer does not set a blended `score` key", "score" not in off_clean)

    print("== 6. policy-ON without creds → outcome unavailable, evals still emit ==")
    # creds come from the environment now; clear them so this exercises the genuine no-creds path
    # regardless of ambient JUDGE_* (e.g. when layer 7 is enabled).
    saved = {
        k: os.environ.pop(k)
        for k in ("JUDGE_BASE_URL", "JUDGE_API_KEY", "JUDGE_BASE_URL", "JUDGE_API_KEY")
        if k in os.environ
    }
    try:
        on_nocreds, _ = P.score_policy_grounding(
            "X [policy: gov-a.md L6-L7].", tmp, {"gov-a.md", "gov-b.md"}, policy_expected=True
        )
    finally:
        os.environ.update(saved)
    check("outcome_available = 0 (no env creds)", on_nocreds["policy_outcome_available"] == 0)
    check(
        "citation evals present",
        on_nocreds.get("policy_citations_in_corpus") == 1 and "policy_file_recall" in on_nocreds,
    )

    print("== 6b. support-free rubric (relevance + existence) scores WITHOUT creds ==")
    # Only citation_support needs an LLM; a rubric with just relevance + existence is fully
    # deterministic and should score even when no judge creds are present.
    saved = {
        k: os.environ.pop(k)
        for k in ("JUDGE_BASE_URL", "JUDGE_API_KEY", "JUDGE_BASE_URL", "JUDGE_API_KEY")
        if k in os.environ
    }
    try:
        det_rubric = [
            {
                "id": "PR1",
                "kind": "relevance",
                "weight": "+1",
                "title": "grounds in governing policy",
            },
            {
                "id": "PC1",
                "kind": "citation_existence",
                "weight": "+1",
                "title": "citations resolve",
            },
        ]
        rew_d, det_d = P.score_policy_grounding(
            "X [policy: gov-a.md L6-L7].",
            tmp,
            {"gov-a.md"},
            policy_expected=True,
            policy_rubrics=det_rubric,
        )
    finally:
        os.environ.update(saved)
    by_d = {x["id"]: x for x in det_d.get("outcome_graded", [])}
    check("support-free rubric graded without creds", rew_d.get("policy_outcome_available") == 1)
    check(
        "PR1 followed (only gov-a, which is gold)", by_d.get("PR1", {}).get("label") == "followed"
    )
    check("PC1 followed (1 valid / 1 total)", by_d.get("PC1", {}).get("label") == "followed")

    print("== 7. correctness bucket + weighted-mean helpers (deterministic) ==")
    check("all valid → followed", P._rate_to_class(3, 3) == "followed")
    check("some valid → partially_followed", P._rate_to_class(1, 3) == "partially_followed")
    check("none valid → did_not_follow", P._rate_to_class(0, 3) == "did_not_follow")
    check("nothing to check → n/a", P._rate_to_class(0, 0) is None)
    g = [
        P._item("PR1", "", "followed", ""),
        P._item("PC1", "", "did_not_follow", ""),
        P._item("PC2", "", None, ""),
    ]  # PC2 not-applicable → excluded from the mean
    sc = P._score_from_labels(g)
    check("n/a item excluded → mean(1.0, 0.0) = 50", sc["pct"] == 50.0, str(sc))

    print("== 7b. policy relevance = deterministic gold-doc membership (no creds) ==")
    check(
        "only gold cited → followed",
        P._relevance_class({"gov-a.md"}, {"gov-a.md", "gov-b.md"}) == "followed",
    )
    check(
        "gold + non-gold cited → partially_followed",
        P._relevance_class({"gov-a.md", "x.md"}, {"gov-a.md"}) == "partially_followed",
    )
    check(
        "no gold cited → did_not_follow",
        P._relevance_class({"x.md"}, {"gov-a.md"}) == "did_not_follow",
    )
    check(
        "nothing cited → did_not_follow",
        P._relevance_class(set(), {"gov-a.md"}) == "did_not_follow",
    )

    # This is the only end-to-end pass over score_policy_grounding with a full 3-item rubric and
    # real judge creds, so it deliberately opts INTO the support check (run_support=True) that the
    # in-trial default leaves off. That is what keeps judge_support and the COMPLETE-outcome key
    # covered; sections 9 and 10 below cover the default post-hoc path, where the support item is
    # not-applicable and the pct is emitted under policy_outcome_pct_deterministic instead.
    print("== 8. full 3-class rubric: relevance + correctness (gated on env creds) ==")
    if os.environ.get("JUDGE_BASE_URL"):
        rubrics = [
            {
                "id": "PR1",
                "kind": "relevance",
                "weight": "+1",
                "title": "Response grounds its determination in the governing guidelines for sepsis bundle timing.",
            },
            {
                "id": "PC1",
                "kind": "citation_existence",
                "weight": "+1",
                "title": "Every policy citation resolves to a real corpus document and a valid line span.",
            },
            {
                "id": "PC2",
                "kind": "citation_support",
                "weight": "+1",
                "title": "Each cited passage factually supports the claim it is attached to.",
            },
        ]
        rep = "Antibiotics within 3 hours per guidance [policy: gov-a.md L6-L7].\n"
        rew, det = P.score_policy_grounding(
            rep,
            tmp,
            {"gov-a.md"},
            policy_expected=True,
            policy_rubrics=rubrics,
            prompt="Was the bundle met?",
            run_support=True,
        )
        graded = det.get("outcome_graded", [])
        by_id = {x["id"]: x for x in graded}
        _CLASSES = ("followed", "partially_followed", "did_not_follow")
        check("outcome graded (available)", rew.get("policy_outcome_available") == 1)
        check("mode = 3class", det.get("outcome_mode") == "3class")
        check("one verdict per item (3)", len(graded) == 3)
        check(
            "PC1 existence graded deterministically = followed (1 valid / 1 total)",
            by_id.get("PC1", {}).get("label") == "followed",
            str(by_id.get("PC1")),
        )
        check(
            "PC2 support judged into the 3-class set (run_support=True)",
            by_id.get("PC2", {}).get("label") in _CLASSES,
            str(by_id.get("PC2")),
        )
        check(
            "support judged => COMPLETE key, not the deterministic-only one",
            "policy_outcome_pct" in rew and "policy_outcome_pct_deterministic" not in rew,
            str(sorted(k for k in rew if k.startswith("policy_outcome_pct"))),
        )
        check(
            "relevance deterministic = followed (cited gov-a.md, the only gold doc)",
            by_id.get("PR1", {}).get("label") == "followed",
            str(by_id.get("PR1")),
        )
        check(
            "pct in [0,100]",
            0.0 <= rew.get("policy_outcome_pct", -1) <= 100.0,
            str(rew.get("policy_outcome_pct")),
        )
        print("     labels:", [(x["id"], x.get("label")) for x in graded])
    else:
        print("  SKIP  (set JUDGE_BASE_URL/JUDGE_API_KEY/JUDGE_MODEL to run the LLM check)")

    # ── support_results semantics: None ("not judged") vs [None] ("judged, nothing supported") ──
    # The trap that silently turned a correct 100% into 66.7% when the in-trial support pass was
    # removed: a citation_support item with NO result must be NOT-APPLICABLE (excluded from the
    # weighted mean), not did_not_follow. Every scenario ships 3 equal-weight items, so conflating the
    # two costs up to 33.3 pts on every policy-ON trial. Guarded here because a future
    # `support_results or []` would reintroduce it with no other test failing.
    print("\n== 9. support_results: None vs [None] vs judged ==")
    rub = [
        {"id": "PR1", "kind": "relevance", "weight": "+1", "title": "relevance"},
        {"id": "PC2", "kind": "citation_support", "weight": "+1", "title": "support"},
        {"id": "PC1", "kind": "citation_existence", "weight": "+1", "title": "existence"},
    ]
    cits = P.parse_citations("A claim [policy: doc.md L1-L2]")
    resolved = [
        {"in_corpus": True, "span_valid": True, "cited_text": "t", "resolved_name": "doc.md"}
    ]

    def _pct(support):
        out = P.grade_policy_outcome(
            True, cits, resolved, {"doc.md"}, "report", rub, "", None, support_results=support
        )
        return out["score"]["pct"], [g["label"] for g in out["graded"]]

    pct_none, lab_none = _pct(None)
    check("None -> support item not_applicable", "not_applicable" in lab_none, str(lab_none))
    check("None -> pct 100 (mean over the 2 scorable items)", pct_none == 100.0, str(pct_none))
    pct_zero, lab_zero = _pct([None])
    check("[None] -> support item did_not_follow", "did_not_follow" in lab_zero, str(lab_zero))
    check("[None] -> pct 66.7 (mean over all 3)", pct_zero == 66.7, str(pct_zero))
    pct_ok, _ = _pct([{"supported": True, "justification": ""}])
    check("judged+supported -> pct 100", pct_ok == 100.0, str(pct_ok))
    check("None and [None] must NOT be equal", pct_none != pct_zero, f"{pct_none} vs {pct_zero}")

    # ── an INCOMPLETE policy outcome must not share a key with a complete one (greptile P1) ──
    # A flag beside the same key gets ignored: metric.py and policy_grounding_summary.py both
    # averaged policy_outcome_pct blind. A distinct key makes mixing structurally impossible.
    print("\n== 10. incomplete policy outcome gets its own key ==")
    rub2 = [
        {"id": "PR1", "kind": "relevance", "weight": "+1", "title": "r"},
        {"id": "PC1", "kind": "citation_existence", "weight": "+1", "title": "e"},
        {"id": "PC2", "kind": "citation_support", "weight": "+1", "title": "s"},
    ]
    rep2 = "Antibiotics were given within 3 hours [policy: gov-a.md L6-L6]"
    rw_inc, _ = P.score_policy_grounding(
        rep2, tmp, {"gov-a.md"}, True, policy_rubrics=rub2, run_support=False
    )
    check(
        "incomplete: policy_outcome_pct ABSENT",
        "policy_outcome_pct" not in rw_inc,
        str(sorted(rw_inc)),
    )
    check(
        "incomplete: deterministic key present",
        "policy_outcome_pct_deterministic" in rw_inc,
        str(sorted(rw_inc)),
    )
    check("incomplete: support_judged=0", rw_inc.get("policy_support_judged") == 0)
    check(
        "incomplete: items_scored=2 (support excluded)",
        rw_inc.get("policy_outcome_items_scored") == 2,
        str(rw_inc.get("policy_outcome_items_scored")),
    )
    # policy-OFF has no citation_support item, so it keeps the normal key
    rw_off, _ = P.score_policy_grounding("no citations", tmp, set(), False, policy_rubrics=None)
    check(
        "policy-OFF still uses policy_outcome_pct",
        "policy_outcome_pct" in rw_off,
        str(sorted(rw_off)),
    )

    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
