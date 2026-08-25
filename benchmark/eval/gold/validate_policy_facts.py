"""validate_policy_facts — assert the corpus still carries each scenario's load-bearing facts.

The corpus is produced by running a VLM over source PDFs, which is not byte-reproducible: a
rebuild can drop a table row or garble a threshold. When that happens the affected rubric item
becomes unsatisfiable for every agent and the benchmark reports a model weakness instead of a
corpus defect. This check turns that silent failure into a loud one.

Facts live in ``policy_facts.json``. Each names a governing doc and the verbatim substrings that
must survive conversion. Matching collapses whitespace, so re-wrapping is tolerated but lost or
altered content is not.

  cd <repo root>
  python benchmark/eval/gold/validate_policy_facts.py                 # uses ./benchmark/corpus
  python benchmark/eval/gold/validate_policy_facts.py --corpus <dir>
  CLINICARE_CORPUS_DIR=<dir> python benchmark/eval/gold/validate_policy_facts.py

Exits non-zero on any miss, so it can gate a corpus build.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCHMARK = HERE.parents[1]
FACTS = HERE / "policy_facts.json"
GOLD = HERE / "policy_gold.json"


def _norm(s: str) -> str:
    """Collapse whitespace so a substring still matches across a re-wrapped line."""
    return re.sub(r"\s+", " ", s).strip()


def load_facts() -> dict[str, list[dict]]:
    raw = json.loads(FACTS.read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def check(corpus_dir: Path, present_only: bool = False) -> tuple[list[str], int, int]:
    """(failures, n_checked, n_skipped). A failure is a missing doc or a missing substring.
    present_only skips documents absent from the corpus instead of failing on them, so a
    partially built corpus can still be checked."""
    facts = load_facts()
    gold = {s["scenario_id"]: set(s["policy_docs"]) for s in json.loads(GOLD.read_text())}
    text_cache: dict[str, str] = {}
    failures: list[str] = []
    n = skipped = 0

    for scenario, entries in facts.items():
        if scenario not in gold:
            failures.append(f"{scenario}: not a scenario in policy_gold.json")
            continue
        for fact in entries:
            doc = fact["doc"]
            if doc not in gold[scenario]:
                failures.append(
                    f"{scenario}/{fact['id']}: {doc} is not a governing doc for this scenario"
                )
                continue
            if doc not in text_cache:
                path = corpus_dir / doc
                if not path.exists():
                    if present_only:
                        skipped += 1
                        continue
                    failures.append(f"{scenario}/{fact['id']}: {doc} missing from corpus")
                    continue
                text_cache[doc] = _norm(path.read_text(errors="replace"))
            body = text_cache[doc]
            for needle in fact["must_contain"]:
                n += 1
                if _norm(needle) not in body:
                    failures.append(
                        f"{scenario}/{fact['id']}: {doc} no longer contains {needle!r} "
                        f"(breaks rubric {', '.join(fact['rubrics'])})"
                    )
    return failures, n, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--present-only",
        action="store_true",
        help="skip documents absent from the corpus rather than failing (partial builds)",
    )
    ap.add_argument(
        "--corpus",
        default=os.environ.get("CLINICARE_CORPUS_DIR") or str(BENCHMARK / "corpus"),
        help="corpus directory (default: $CLINICARE_CORPUS_DIR or benchmark/corpus)",
    )
    args = ap.parse_args()
    corpus_dir = Path(args.corpus)
    if not corpus_dir.is_dir():
        print(f"corpus dir not found: {corpus_dir}", file=sys.stderr)
        return 2

    failures, n, skipped = check(corpus_dir, args.present_only)
    facts = load_facts()
    n_facts = sum(len(v) for v in facts.values())
    if failures:
        print(f"FAIL — {len(failures)} problem(s) across {n_facts} facts / {n} assertions\n")
        for f in failures:
            print(f"  {f}")
        return 1
    tail = f"  ({skipped} skipped — document not built)" if skipped else ""
    print(f"OK — {n_facts} facts / {n} assertions across {len(facts)} scenarios{tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
