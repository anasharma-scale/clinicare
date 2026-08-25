"""Build the per-scenario REQUIRED-EVIDENCE rubric that insights_recall (R_finding) scores against.

`metadata_required_evidence` (the edited `turn_1_edited_required_evidence` when present) in the
CliniCARE-Bench annotation is the MEDICAL EXPERT'S statement of what evidence each task requires —
a scenario-level checklist of decisive evidence categories (all 25 scenarios have it; 13 edited).
This distils it into a clean per-scenario category list that drives insights_recall two ways:
  - decisive filter: a consensus/deterministic insight counts toward gold only if it maps to a
    required category (decisive vs incidental);
  - narrative schema: for categories with no hard-atom fact (e.g. goals-of-care code-status),
    the category itself is the gold, scored by an LLM coverage check against the report.

The rubric is SCENARIO-LEVEL: the same categories apply to every patient of a scenario, and
coverage is scored per category rather than against per-patient facts.

The annotation names tasks "Task N — ..." while everything else keys on the scenario id, so the
two are joined on the task NUMBER, resolved from `_scenarios/` by `core.scenarios` (shared with
the other metrics that need the same join). Matching on title text instead is unreliable — some
scenario names share no token with their task title at all.

  cd <repo root>
  # --annotation is your own copy of the delivery CSV (see build_gold.py)
  python benchmark/eval/gold/build_required_evidence.py \
      --annotation benchmark/eval/annotation/<delivery>.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from clinicare_core import load_env
from clinicare_core.paths import bootstrap

HERE = Path(__file__).resolve().parent

bootstrap(__file__, "grounding", "eval")
from core.scenarios import task_by_slug  # noqa: E402
from insight_grounding_llm import _call, _json_array, make_client  # noqa: E402

csv.field_size_limit(10**9)

# slug -> the annotation's task number. DERIVED, not hand-listed: `_scenarios/` is the source
# of truth for the ordering and the annotation's "Task N" follows the `scenario-NN-` dir
# prefix, so adding or renumbering a scenario cannot leave this behind.
SLUG_TASK = task_by_slug()

DEFAULT_ANNOTATION = (
    ""  # the clinician annotation delivery; not publicly distributed (see the note above)
)

_EXTRACT_PROMPT = """This is a medical expert's statement of the evidence REQUIRED to answer a \
clinical deep-research task. Distil it into the distinct required-evidence CATEGORIES — each a \
separate kind of CONTENT/finding the report must cover to be complete.

Rules:
- A category = a distinct kind of evidence CONTENT, NOT a document type or data source. Do NOT \
split one requirement across sources or note types: "discharge + consult/progress notes for \
code-status" is ONE category ("code-status documentation"), not several.
- Merge overlapping / near-duplicate requirements into a single category.
- Keep genuine process requirements (e.g. "an explicit negative search result when concluding \
absence").
- Prefer the MINIMAL set of distinct decisive requirements (usually 3-8). Do not invent \
requirements not implied by the text.

REQUIRED-EVIDENCE TEXT:
{text}

Return ONLY a JSON array of short strings.
"""


def _task_number(name: str) -> int | None:
    m = re.search(r"Task\s+(\d+)", name or "")  # search, not match: names may start with "**"
    return int(m.group(1)) if m else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--annotation", default=DEFAULT_ANNOTATION, help="path to the delivery CSV")
    ap.add_argument("--out", type=Path, default=HERE / "required_evidence.json")
    ap.add_argument("--dry-run", action="store_true", help="print slug->task/source map, no LLM")
    args = ap.parse_args()

    rows_by_task: dict[int, dict] = {}
    with open(args.annotation, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            n = _task_number(r.get("metadata_task_name", ""))
            if n is not None:
                rows_by_task[n] = r

    client = model = None
    if not args.dry_run:
        env = load_env()
        client = make_client(env)
        model = (env.get("JUDGE_MODEL") or "openai/gpt-5.5").split("/")[-1]

    out: dict[str, dict] = {}
    for slug, task in SLUG_TASK.items():
        row = rows_by_task.get(task)
        if row is None:
            print(f"  ! {slug}: no Task {task} row in annotation", file=sys.stderr)
            continue
        edited = (row.get("turn_1_edited_required_evidence") or "").strip()
        text = edited or (row.get("metadata_required_evidence") or "").strip()
        source = "edited" if edited else "base"
        if args.dry_run:
            print(f"  {slug:24s} Task {task:<2d} [{source}]  {len(text):4d} chars")
            continue
        cats = [
            c.strip()
            for c in _json_array(_call(client, model, _EXTRACT_PROMPT.format(text=text)))
            if isinstance(c, str) and c.strip()
        ]
        out[slug] = {
            "task": task,
            "task_name": row.get("metadata_task_name", "").replace("*", "").strip(),
            "source": source,
            "categories": cats,
        }
        print(f"  {slug:24s} Task {task:<2d} [{source}]  {len(cats)} categories")

    if args.dry_run:
        return
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nwrote {len(out)} scenario rubrics → {args.out}")


if __name__ == "__main__":
    main()
