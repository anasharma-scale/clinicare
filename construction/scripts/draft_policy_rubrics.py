"""Seed a per-scenario policy-relevance rubric (``_scenarios/<scenario>/policy_rubrics.toml``) from the
governing-document list in ``eval/gold/policy_gold.json``.

This produces a STARTING DRAFT for expert refinement — a topic-framed relevance statement plus
the two generic citation-correctness items (existence + support) — in the ``[[rubric]]`` schema
build_tasks reads. The healthcare verifier (``judge.py`` + ``policy_scoring.py``) grades each item
into followed / partially_followed / did_not_follow (1.0 / 0.5 / 0.0) — relevance & support via
the LLM, existence deterministically — against the agent's report + its resolved policy citations
on the policy-ON condition (policy-OFF uses a fixed abstention check, so no per-scenario authoring is
needed there). The overall policy outcome is the weighted mean of the per-item class scores.

Edit the generated files freely: tighten the relevance statement/topic, or add scenario-specific
relevance statements (e.g. "grounds the dosing threshold in the governing guideline"). Re-running
this script SKIPS scenarios that already have a ``policy_rubrics.toml`` unless ``--overwrite`` is
given, so it won't clobber expert edits.

  cd <repo root>
  python construction/scripts/draft_policy_rubrics.py            # seed missing files
  python construction/scripts/draft_policy_rubrics.py --overwrite   # regenerate all
  python construction/scripts/draft_policy_rubrics.py sepsis-bundle # one scenario
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent  # construction/scripts/
ROOT = HERE.parents[1]  # repo root
BENCHMARK = ROOT / "benchmark"
SCENARIOS_DIR = BENCHMARK / "_scenarios"
POLICY_GOLD = BENCHMARK / "eval" / "gold" / "policy_gold.json"


def _authoritative_block(grounding_requirements: str) -> str:
    """The 'Authoritative ... sources' section of a scenario's grounding_requirements (prose list of
    the guideline titles the governing documents correspond to)."""
    m = re.search(r"authoritative[^\n]*sources", grounding_requirements or "", re.IGNORECASE)
    return grounding_requirements[m.start() :].strip() if m else ""


_TOPIC_PROMPT = """You are helping write a clinical policy-grounding rubric. Given a task and the \
authoritative guideline / policy sources a domain expert considers governing for it, write ONE \
concise noun phrase naming the CLINICAL / POLICY DOMAIN those sources collectively govern for this \
task — broad enough to encompass ALL the listed sources (not just the narrow task label), specific \
to the scenario, lowercase, no trailing period. It will be dropped into rubric sentences like:
  "...guidelines a domain expert would consider governing for <PHRASE>"
  "...blanket or definitive claims about <PHRASE> without any policy citation"

## Task
{task}

## Authoritative sources the governing documents correspond to
{sources}

Output ONLY the phrase."""


def synthesize_topic(scenario: dict, creds: dict | None) -> str:
    """An encompassing statement of the policy domain the scenario's governing docs cover, synthesized
    from the clinical question + authoritative-sources block. Falls back to ``description`` when no
    LLM creds (or on any error), so the seeder still runs offline."""
    description = (scenario.get("description") or "").strip()
    if not (creds and creds.get("base_url") and creds.get("api_key")):
        return description
    task = (scenario.get("clinical_question") or scenario.get("prompt") or description).strip()
    sources = _authoritative_block(scenario.get("grounding_requirements", "")) or "(not listed)"
    try:
        from openai import OpenAI

        client = OpenAI(base_url=creds["base_url"], api_key=creds["api_key"])
        resp = client.chat.completions.create(
            model=creds["model"],
            temperature=0,
            max_tokens=200,
            messages=[
                {"role": "user", "content": _TOPIC_PROMPT.format(task=task, sources=sources)}
            ],
        )
        phrase = (resp.choices[0].message.content or "").strip()
        phrase = next(
            (ln.strip().strip('"').rstrip(".") for ln in phrase.splitlines() if ln.strip()), ""
        )
        return phrase or description
    except Exception as exc:  # noqa: BLE001
        print(
            f"    ! topic synthesis failed ({type(exc).__name__}) — using description",
            file=sys.stderr,
        )
        return description


def _load_env_creds() -> dict | None:
    """JUDGE_* creds from the environment or the repo-root .env (topic-synthesis LLM call)."""
    env = dict(os.environ)
    dot = ROOT / ".env"
    if dot.exists():
        parsed = {}
        for line in dot.read_text().splitlines():
            m = re.match(r"\s*([A-Z_]+)=(.*)", line)
            if m:
                parsed[m.group(1)] = m.group(2).strip()
        exp = lambda v: re.sub(r"\$\{(\w+)\}", lambda x: parsed.get(x.group(1), ""), v)
        parsed = {k: exp(v) for k, v in parsed.items()}
        env = {**parsed, **env}  # real environment wins
    base = env.get("JUDGE_BASE_URL")
    key = env.get("JUDGE_API_KEY")
    model = env.get("JUDGE_MODEL") or env.get("POLICY_TOPIC_MODEL")
    if base and key:  # model may be supplied via --model; resolved in main()
        return {"base_url": base, "api_key": key, "model": model}
    return None


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def render_toml(scenario_id: str, topic: str, docs: list[str]) -> str:
    """Seed a scenario's 3-class policy outcome rubric — a topic-framed RELEVANCE statement plus the
    two generic CITATION-CORRECTNESS items (existence + support). Each is classified (policy-ON)
    into followed / partially_followed / did_not_follow and the scores are averaged. Relevance
    items are DOCUMENT-level and TOPIC-framed — keep wording generic; do NOT hardcode doc names.

    A single interpretable class per item is steadier across judge models than a signed
    MUST-DO/MUST-NOT sum would be. Both policy axes (relevance + citation correctness) are graded
    here as rubric line items, dispatched by ``kind``.
    """
    topic = _esc((topic or scenario_id).strip().rstrip("."))
    return "\n".join(
        [
            f"# Policy outcome rubric for {scenario_id} — 3-class, judged on the policy-ON condition.",
            "# SEEDED from policy_gold.json + scenario.toml; EDIT freely. Each item is classified into one of",
            "# three classes and the per-item scores are AVERAGED into the policy outcome:",
            "#   followed (1.0)   partially_followed (0.5)   did_not_follow (0.0)",
            "#",
            "# NOTE on PR1: graded DETERMINISTICALLY by gold-doc membership —",
            "# followed = cited ONLY governing (gold) documents; partially_followed = cited >=1 governing",
            "# doc BUT also cited non-governing ones; did_not_follow = cited no governing doc. The governing",
            "# set is this scenario's list in eval/gold/policy_gold.json — curate THAT list (not the",
            "# wording) to change what counts as governing (e.g. drop a non-authoritative doc).",
            "#",
            "# `kind` selects how an item is graded (do NOT change it): 'relevance' = DETERMINISTIC gold-doc",
            "# membership (see the PR1 note above — no LLM); 'citation_existence' = deterministic (do the",
            "# citations resolve to a real corpus doc + valid line span); 'citation_support' = LLM judges",
            "# whether each cited passage backs its claim. `weight` scales an item's share of the mean.",
            "",
            "# ── Policy relevance ─────────────────────────────────────────────────────────",
            "[[rubric]]",
            'id = "PR1"',
            'kind = "relevance"',
            'weight = "+1"',
            f'title = "Response grounds its determination in the policy or care guidelines a domain '
            f'expert would consider governing for {topic}."',
            "",
            "# ── Policy citation correctness (generic; applies to every scenario) ─────────────",
            "[[rubric]]",
            'id = "PC1"',
            'kind = "citation_existence"',
            'weight = "+1"',
            'title = "Every policy citation resolves to a real corpus document and a valid line span '
            '(no fabricated or out-of-corpus citations)."',
            "",
            "[[rubric]]",
            'id = "PC2"',
            'kind = "citation_support"',
            'weight = "+1"',
            'title = "Each cited passage factually supports the specific claim it is attached to '
            '(genuine documentary attribution, not merely on-topic or fabricated)."',
            "",
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "scenarios", nargs="*", help="scenario id(s) to seed (default: all in policy_gold.json)"
    )
    ap.add_argument("--overwrite", action="store_true", help="regenerate files that already exist")
    ap.add_argument(
        "--no-llm",
        action="store_true",
        help="skip topic synthesis; use the terse scenario description",
    )
    ap.add_argument(
        "--print-topics",
        action="store_true",
        help="print the synthesized topic per scenario; write nothing",
    )
    ap.add_argument(
        "--model", help="override the topic-synthesis model (default JUDGE_MODEL / env)"
    )
    args = ap.parse_args()

    if not POLICY_GOLD.exists():
        sys.exit(f"{POLICY_GOLD} not found — build the gold first")
    gold = {
        g["scenario_id"]: list(g.get("policy_docs", []))
        for g in json.loads(POLICY_GOLD.read_text())
    }

    creds = None if args.no_llm else _load_env_creds()
    if creds:
        creds["model"] = args.model or creds.get("model")
        if not creds["model"]:  # base+key but no model anywhere → can't call
            creds = None
    if not creds and not args.no_llm:
        print(
            "  note: no LLM creds+model (JUDGE_BASE_URL/JUDGE_API_KEY/JUDGE_MODEL or --model) — "
            "topics fall back to the scenario description; pass --no-llm to silence.",
            file=sys.stderr,
        )

    # scenario_id -> (scenario dir, full scenario dict) via each scenario.toml (id, as build_tasks.py sees it).
    dir_by_id: dict[str, tuple[Path, dict]] = {}
    for d in sorted(SCENARIOS_DIR.iterdir()):
        ct = d / "scenario.toml"
        if ct.exists():
            scenario = tomllib.loads(ct.read_text())
            dir_by_id[scenario["id"]] = (d, scenario)

    want = set(args.scenarios) if args.scenarios else set(gold)
    wrote = skipped = 0
    for scenario_id in sorted(want):
        docs = gold.get(scenario_id)
        if docs is None:
            print(f"  ! {scenario_id}: not in policy_gold.json — skipping", file=sys.stderr)
            continue
        entry = dir_by_id.get(scenario_id)
        if entry is None:
            print(f"  ! {scenario_id}: no matching scenario dir — skipping", file=sys.stderr)
            continue
        scenario_dir, scenario = entry
        topic = synthesize_topic(scenario, creds)
        if args.print_topics:
            print(f"  {scenario_id}: {topic}")
            continue
        out = scenario_dir / "policy_rubrics.toml"
        if out.exists() and not args.overwrite:
            print(f"  = {scenario_id}: policy_rubrics.toml exists — skip (use --overwrite)")
            skipped += 1
            continue
        out.write_text(render_toml(scenario_id, topic, docs))
        print(f"  + {scenario_id}: topic={topic!r}")
        wrote += 1

    if not args.print_topics:
        print(
            f"\nseeded {wrote} file(s), skipped {skipped}. REVIEW/refine each policy_rubrics.toml."
        )


if __name__ == "__main__":
    main()
