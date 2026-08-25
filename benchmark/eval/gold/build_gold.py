"""Build the derived gold-sources file for evidence_retrieval_recall from the clinician
annotation delivery CSV.

That delivery is a task-spec review containing MIMIC-note-derived clinical text (worked
examples, evidence prose), so it is covered by the MIMIC DUA and is NOT distributed with this
repo. Supply your own copy. This distils it to the only thing the metric needs — per scenario,
the task title and the set of required MIMIC source tables — and that distilled JSON
(gold_sources.json) carries no clinical content, which is why it IS committed. You therefore
do not need to run this to use the benchmark.

  cd <repo root>
  python benchmark/eval/gold/build_gold.py --annotation path/to/annotation.csv

Authoritative grounding text per scenario = the edited field if present, else the original.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from clinicare_core.paths import bootstrap

HERE = Path(__file__).resolve().parent

bootstrap(__file__, "grounding")
from evidence_retrieval_recall import GOLD_VOCAB, canon  # noqa: E402

# The clinician annotation delivery this distils. It is a MIMIC-derived working artifact
# and is NOT publicly distributed, so there is no default — pass --annotation with your
# own copy. The OUTPUT (gold_sources.json) is committed, so you do not need to re-run
# this to use the benchmark; it is here to document how that gold was derived.
DEFAULT_ANNOTATION = (
    ""  # the clinician annotation delivery; not publicly distributed (see the note above)
)

csv.field_size_limit(10**9)
_TABLE_RX = re.compile(r"\b(" + "|".join(sorted(GOLD_VOCAB, key=len, reverse=True)) + r")\b", re.I)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--annotation",
        default=DEFAULT_ANNOTATION,
        help="path to the clinician annotation CSV",
    )
    ap.add_argument("--out", type=Path, default=HERE / "gold_sources.json")
    args = ap.parse_args()

    gold = []
    for r in csv.DictReader(open(args.annotation, newline="")):
        text = (r.get("turn_1_edited_grounding_requirements") or "").strip() or (
            r.get("metadata_grounding_requirements") or ""
        )
        raw = {m.group(1).lower() for m in _TABLE_RX.finditer(text)}
        gold.append(
            {
                "title": r["metadata_task_name"].replace("*", "").strip(),
                "tables": sorted(canon(raw)),
            }
        )

    args.out.write_text(json.dumps(gold, indent=2) + "\n")
    print(f"wrote {len(gold)} scenarios → {args.out}")


if __name__ == "__main__":
    main()
