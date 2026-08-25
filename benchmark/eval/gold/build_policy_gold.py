"""Build the derived POLICY gold file for the policy-grounding metric.

For each scenario, the expert "Authoritative public sources" are listed in
``_scenarios/<scenario>/scenario.toml`` under ``grounding_requirements`` as **free-text prose titles**
(e.g. "Society of Critical Care Medicine, Surviving Sepsis Campaign (2026)") — NOT corpus
filenames. This script maps those titles to the actual ``corpus/*.md`` filenames the agent
can cite, using an LLM (the corpus is small, a few dozen docs, so this is reliable), and writes a
draft ``policy_gold.json`` for **human review**.

  cd <repo root>
  # needs an OpenAI-compatible LLM (the judge endpoint): JUDGE_BASE_URL / JUDGE_API_KEY / JUDGE_MODEL
  python benchmark/eval/gold/build_policy_gold.py
  # dry-run without the LLM — just dump the extracted prose + corpus index for eyeballing
  python benchmark/eval/gold/build_policy_gold.py --dry-run

Output schema (one entry per scenario):
  {"scenario_id", "title", "policy_docs": ["<file>.md", ...], "notes": "<review hints>"}

The gold is file-level only — documents, not line spans (experts do not annotate line
numbers). The policy metric therefore scores file-level retrieval + citation validity, not
span-level recall. Review the draft before committing: spot-check that each scenario's docs are
the ones a domain expert would consider governing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path

from clinicare_core.paths import bootstrap

HERE = Path(__file__).resolve().parent
HEALTHCARE = HERE.parents[1]
SCENARIOS_DIR = HEALTHCARE / "_scenarios"
# The corpus is assembled locally, not repo content (benchmark/corpus/README.md);
# CLINICARE_CORPUS_DIR points at the directory acquire_corpus.py built.
CORPUS_DIR = Path(os.environ.get("CLINICARE_CORPUS_DIR") or (HEALTHCARE / "corpus"))

bootstrap(__file__, "container_tests")

import os  # noqa: E402


def authoritative_block(grounding_requirements: str) -> str:
    """The 'Authoritative ... sources' section of a scenario's grounding_requirements (prose)."""
    m = re.search(r"authoritative[^\n]*sources", grounding_requirements, re.IGNORECASE)
    return grounding_requirements[m.start() :].strip() if m else ""


def corpus_index() -> list[dict]:
    """[{file, title, heading}] for every corpus doc — the candidate set for matching."""
    out = []
    for p in sorted(CORPUS_DIR.glob("*.md")):
        text = p.read_text(errors="replace")
        tm = re.search(r'^title:\s*"?(.*?)"?\s*$', text, re.MULTILINE)
        hm = re.search(r"^#+\s*(.+)$", text, re.MULTILINE)
        out.append(
            {
                "file": p.name,
                "title": (tm.group(1).strip() if tm else ""),
                "heading": (hm.group(1).strip() if hm else ""),
            }
        )
    return out


def _match_prompt(scenario_id: str, sources: str, index: list[dict]) -> str:
    lines = [f"- {d['file']}  |  {d['heading'] or d['title']}" for d in index]
    catalog = "\n".join(lines)
    return f"""You map expert-named authoritative policy/guideline sources to the files in a \
document corpus. Match by the DOCUMENT'S IDENTITY (issuing body, guideline name, topic, year), \
NOT by filename string similarity — many filenames are opaque publisher IDs, so use the title/\
heading shown.

## Scenario: {scenario_id}
## Expert "authoritative sources" for this scenario (free text)
{sources}

## Corpus catalog (filename  |  document title/heading)
{catalog}

Return the corpus files that correspond to the expert sources above. Include a file only if you \
are reasonably confident it IS one of the named sources (or the clearly-equivalent published \
version). Do NOT invent files not in the catalog. If an expert source has no corpus match, omit \
it. Respond with a JSON array and nothing else:
[{{"doc": "<exact filename from the catalog>", "confidence": "high" or "low", "reason": "which expert source it matches"}}]"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=HERE / "policy_gold.json")
    ap.add_argument("--model", default=os.environ.get("JUDGE_MODEL", "openai/gpt-5.5"))
    ap.add_argument("--base-url", default=os.environ.get("JUDGE_BASE_URL", ""))
    ap.add_argument("--api-key", default=os.environ.get("JUDGE_API_KEY", ""))
    ap.add_argument(
        "--dry-run", action="store_true", help="print extracted prose + catalog, no LLM"
    )
    args = ap.parse_args()

    index = corpus_index()
    valid_files = {d["file"] for d in index}
    scenario_dirs = sorted(d for d in SCENARIOS_DIR.iterdir() if (d / "scenario.toml").exists())

    if args.dry_run:
        print("=== corpus catalog ===")
        for d in index:
            print(f"  {d['file']}  |  {d['heading'] or d['title']}")
        print("\n=== per-scenario authoritative sources ===")
        for cd in scenario_dirs:
            scenario = tomllib.loads((cd / "scenario.toml").read_text())
            print(f"\n--- {scenario['id']} ---")
            print(authoritative_block(scenario.get("grounding_requirements", "")) or "  (none)")
        return

    if not (args.base_url and args.api_key):
        sys.exit("JUDGE_BASE_URL / JUDGE_API_KEY required (or use --dry-run)")

    from policy_scoring import _call_judge

    gold = []
    for cd in scenario_dirs:
        scenario = tomllib.loads((cd / "scenario.toml").read_text())
        scenario_id = scenario["id"]
        sources = authoritative_block(scenario.get("grounding_requirements", ""))
        if not sources:
            print(f"  ! {scenario_id}: no authoritative-sources block", file=sys.stderr)
            gold.append(
                {
                    "scenario_id": scenario_id,
                    "title": scenario.get("description", ""),
                    "policy_docs": [],
                    "notes": "no authoritative-sources block in scenario.toml",
                }
            )
            continue
        matches = _call_judge(
            _match_prompt(scenario_id, sources, index), args.model, args.base_url, args.api_key
        )
        docs, low = [], []
        for m in matches:
            doc = (m.get("doc") or "").strip()
            if doc not in valid_files:
                print(
                    f"  ! {scenario_id}: LLM returned unknown file {doc!r} — dropped",
                    file=sys.stderr,
                )
                continue
            docs.append(doc)
            if (m.get("confidence") or "").lower() != "high":
                low.append(f"{doc}: {m.get('reason', '')}")
        notes = "REVIEW low-confidence: " + "; ".join(low) if low else "review"
        gold.append(
            {
                "scenario_id": scenario_id,
                "title": scenario.get("description", ""),
                "policy_docs": sorted(set(docs)),
                "notes": notes,
            }
        )
        print(
            f"  {scenario_id}: {len(docs)} doc(s){' [' + str(len(low)) + ' low-conf]' if low else ''}"
        )

    args.out.write_text(json.dumps(gold, indent=2) + "\n")
    print(
        f"\nwrote {len(gold)} scenarios → {args.out}\n(REVIEW the draft — especially entries with 'low-conf' notes.)"
    )


if __name__ == "__main__":
    main()
