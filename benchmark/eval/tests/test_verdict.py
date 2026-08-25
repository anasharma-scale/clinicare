"""Tests for the PRIMARY reward: verdict extraction and the 4-class label match.

`judge.py::_extract_outcome_label` + `_label_match` decide `reward.json:score` for every trial, and
they are the benchmark's anti-gaming anchor. The contract they enforce is *not* obvious from reading
either function, and every clause exists because a naive parser would let an agent score without
committing to an answer:

  * only the FIRST verdict-marker line counts — otherwise an agent hedges, then appends a clean line
  * that line must resolve to EXACTLY ONE label — otherwise "Yes / No / Indeterminate" matches the
    key by enumeration
  * a bare "Indeterminate" resolves to NOTHING — the two subtypes imply different downstream
    actions (retrieve more evidence vs escalate to an expert), so the distinction cannot be skipped
  * a verdict word in prose must NOT match — only a line-leading marker does
  * unparseable is scored INCORRECT, never dropped from the denominator

None of that was covered by a test, on the one metric every headline number rests on. A refactor
that broke any clause would silently inflate or deflate accuracy for every system at once, with no
other test failing.

    python benchmark/eval/tests/test_verdict.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HC = Path(__file__).resolve().parents[2]  # benchmark
_spec = importlib.util.spec_from_file_location("_judge", HC / "_template" / "tests" / "judge.py")
J = importlib.util.module_from_spec(_spec)
sys.modules["_judge"] = J
_spec.loader.exec_module(J)

YES, NO = "YES", "NO"
LACK = "INDETERMINATE_LACK_OF_DATA"
AMB = "INDETERMINATE_MEDICAL_AMBIGUITY"

_fails: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(
        f"  {'ok  ' if cond else 'FAIL'}  {label}"
        + (f"   [{detail}]" if detail and not cond else "")
    )
    if not cond:
        _fails.append(label)


def lbl(report: str):
    return J._extract_outcome_label(report)


def main() -> int:
    print("== 1. the four canonical labels parse from the designated line ==")
    for text, want in [
        ("## Answer: Yes", YES),
        ("## Answer: No", NO),
        ("## Answer: Indeterminate – lack of data", LACK),
        ("## Answer: Indeterminate – medical ambiguity", AMB),
    ]:
        got = lbl(text)
        check(f"{text!r} -> {want}", got == want, str(got))

    print("\n== 2. formatting tolerance (agents drift; the contract must not) ==")
    for text, want in [
        ("**Answer:** Yes", YES),  # bold instead of heading
        ("### Verdict: No", NO),  # alternate keyword + depth
        ("Final answer: Yes", YES),  # prose-style marker at line start
        ("## Determination — No", NO),  # em-dash separator
        ("## answer: yes", YES),  # case-insensitive
        ("## Answer\nYes", YES),  # label on the NEXT line
        ("## Answer: Indeterminate - insufficient data", LACK),  # ASCII hyphen + synonym
        ("Some prose.\n\n## Answer: No\n\nMore prose.", NO),  # embedded in a report
    ]:
        got = lbl(text)
        check(f"{text.replace(chr(10), chr(92) + 'n')!r} -> {want}", got == want, str(got))

    print("\n== 3. ANTI-GAMING: enumerating labels must not match the key ==")
    for text in [
        "## Answer: Yes / No / Indeterminate – lack of data",
        "## Answer: Yes or No",
        "## Answer: Yes, not No",
        "## Answer: No — unless you consider it Yes",
    ]:
        got = lbl(text)
        check(f"multi-label slot -> None: {text[:46]!r}", got is None, str(got))

    print("\n== 4. ANTI-GAMING: a bare 'Indeterminate' names no resolvable label ==")
    # The two subtypes imply different downstream actions, so the agent must pick one.
    for text in ["## Answer: Indeterminate", "## Answer: indeterminate."]:
        got = lbl(text)
        check(f"bare indeterminate -> None: {text!r}", got is None, str(got))

    print("\n== 5. ANTI-GAMING: only the FIRST marker line is authoritative ==")
    # An agent must not be able to hedge and then append a clean verdict.
    hedged = "## Answer: Yes / No\n\n## Answer: Yes"
    check("hedge-then-clean does NOT rescue the verdict", lbl(hedged) is None, str(lbl(hedged)))
    two = "## Answer: No\n\n## Answer: Yes"
    check("first of two clean markers wins", lbl(two) == NO, str(lbl(two)))
    # A heading marker is preferred over an earlier prose "Answer:" inside an explanation section.
    reasoning_first = "## Explanation\nThe answer: it depends on the baseline.\n\n## Answer: Yes"
    check(
        "heading marker beats an earlier prose 'answer:'",
        lbl(reasoning_first) == YES,
        str(lbl(reasoning_first)),
    )

    print("\n== 6. a verdict word in prose must not be mistaken for the verdict ==")
    for text in [
        "The evidence is a clear Yes on the imaging question.",
        "We cannot say No with confidence.",
        "This is indeterminate for lack of data in the usual sense.",
    ]:
        got = lbl(text)
        check(f"prose only -> None: {text[:44]!r}", got is None, str(got))
    check("empty report -> None", lbl("") is None)

    print("\n== 7. _label_match: 4-way exact, with the one ESCALATE concession ==")
    for agent, gt, want in [
        (YES, YES, True),
        (NO, NO, True),
        (LACK, LACK, True),
        (AMB, AMB, True),
        # the two indeterminate SUBTYPES are distinct and must not cross-credit
        (LACK, AMB, False),
        (AMB, LACK, False),
        (YES, NO, False),
        (YES, LACK, False),
        # silver 3-class gold folds both subtypes into ESCALATE, which is not recoverable, so
        # either indeterminate is accepted against it -- and ONLY against it
        (LACK, "ESCALATE", True),
        (AMB, "ESCALATE", True),
        (YES, "ESCALATE", False),
    ]:
        got = J._label_match(agent, gt)
        check(f"match({agent[:22]}, {gt[:22]}) == {want}", got == want, str(got))
    check("empty agent label never matches", not J._label_match("", YES))
    check("empty gold never matches", not J._label_match(YES, ""))

    print("\n== 8. an unparseable verdict is scored INCORRECT, not excluded ==")
    # `score` must exist and be 0 for a report with no resolvable verdict: dropping it from the
    # denominator instead would quietly raise every system's accuracy.
    check(
        "None label + real gold does not match",
        not J._label_match(lbl("no verdict here") or "", YES),
    )

    print()
    if _fails:
        print(f"{len(_fails)} FAILURE(S): " + "; ".join(_fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
