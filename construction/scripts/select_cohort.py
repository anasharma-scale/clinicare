"""Populate silver_patients.csv per scenario from its cohort SQL (deterministic silver labels).

Step 1 of the label pipeline — see construction/README.md for the whole loop. For every scenario
with a `construction/cohorts/<scenario-dir>.sql`, run it against the MIMIC backend, bucket the rows
by expected_label, sample a balanced evenly-spread set (--per-label of each class), and write the
scenario's params plus an expected_label column. Scenarios with no cohort SQL (the note-dependent
ones) are skipped — those cohorts were built separately. Idempotent.

SILVER, NOT GOLD. These labels are a sampling stratifier, never ground truth: the published gold
labels are the adjudicated consensus in the cohort bundle's full750.csv, which this script does not
and cannot reproduce.

Needs a configured MIMIC backend (see DATA_ACCESS.md):

  python construction/scripts/select_cohort.py                    # every scenario with cohort SQL
  python construction/scripts/select_cohort.py post-ct-aki --per-label 5
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import tomllib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent  # construction/scripts/
CONSTRUCTION = SCRIPTS.parent  # construction/
ROOT = CONSTRUCTION.parent  # repo root
SCENARIOS_DIR = ROOT / "benchmark" / "_scenarios"
# The cohort SQL lives beside the rest of the construction tooling, NOT in the scenario dirs:
# it defines how a cohort was selected, which is benchmark *construction*, and keeping it out
# of benchmark/_scenarios/ stops it reading as something you need in order to run the
# benchmark. One file per scenario dir, named for that dir (so the 01..25 ordering survives).
COHORTS_DIR = CONSTRUCTION / "cohorts"


def spread(cands: list, k: int) -> list:
    """Up to k items spread evenly across the (already sorted) candidate list."""
    if len(cands) <= k:
        return cands
    step = len(cands) / k
    return [cands[int(i * step)] for i in range(k)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "scenarios", nargs="*", help="scenario id(s) to populate (default: all with cohort SQL)"
    )
    ap.add_argument(
        "--per-label", type=int, default=20, help="rows per label per scenario (default 20)"
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="if set, randomly sample each label bucket with this seed (reproducible). "
        "Default: no seed → deterministic evenly-spread systematic sample.",
    )
    args = ap.parse_args()

    from mimic_tools import db

    # Pair each scenario dir with its cohort SQL by dir name (construction/cohorts/<dir>.sql).
    # A scenario without one is simply skipped, same as before the SQL moved out of the
    # scenario dirs; a .sql with no matching scenario dir is a rename that lost its partner,
    # which is worth failing on rather than silently ignoring.
    scenario_dirs = sorted(
        d for d in SCENARIOS_DIR.iterdir() if (COHORTS_DIR / f"{d.name}.sql").is_file()
    )
    orphans = sorted(
        p.name for p in COHORTS_DIR.glob("*.sql") if not (SCENARIOS_DIR / p.stem).is_dir()
    )
    if orphans:
        sys.exit(f"cohort SQL with no matching scenario dir: {orphans}")
    if args.scenarios:
        want = set(args.scenarios)
        scenario_dirs = [
            d
            for d in scenario_dirs
            if tomllib.loads((d / "scenario.toml").read_text())["id"] in want
        ]
        if not scenario_dirs:
            sys.exit(f"no cohort SQL matched {sorted(want)}")

    shortfalls: list[str] = []  # scenarios whose pool couldn't fill a stratum to --per-label
    for d in scenario_dirs:
        scenario = tomllib.loads((d / "scenario.toml").read_text())
        cid, params = scenario["id"], scenario["params"]
        _, rows, _ = db.fetch((COHORTS_DIR / f"{d.name}.sql").read_text(), max_rows=500_000)

        buckets: dict[str, list] = {}
        for r in rows:
            buckets.setdefault(r["expected_label"], []).append(r)

        labels = ("YES", "NO", "ESCALATE")
        picked = []
        for label in labels:
            # Sort first so the base order is canonical regardless of DB fetch order — makes both
            # the systematic spread and the seeded shuffle reproducible run-to-run.
            cand = sorted(buckets.get(label, []), key=lambda r: tuple(r[p] for p in params))
            if args.seed is not None:
                # Per-label seed so one bucket's size doesn't perturb another's draw.
                random.Random(f"{args.seed}:{label}").shuffle(cand)
                picked += cand[: args.per_label]
            else:
                picked += spread(cand, args.per_label)

        out = d / "silver_patients.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(params + ["expected_label"])
            for r in picked:
                w.writerow([r[p] for p in params] + [r["expected_label"]])

        pool = {l: len(buckets.get(l, [])) for l in labels}
        got = {l: sum(1 for r in picked if r["expected_label"] == l) for l in labels}
        # Guard: a stratum that can't reach --per-label means the cohort SQL pool is too small
        # (e.g. a filter tightened too far) — flag it so the shortfall isn't discovered only
        # later as an unbalanced 30-sample.
        short = [l for l in labels if got[l] < args.per_label]
        mark = f"  ⚠ SHORT (< {args.per_label}): {', '.join(short)}" if short else ""
        if short:
            shortfalls.append(
                f"{cid}: " + ", ".join(f"{l}={got[l]}/{args.per_label}" for l in short)
            )
        print(
            f"{cid}: pool {dict(pool)} → wrote "
            + " + ".join(f"{got[l]} {l}" for l in labels)
            + mark
        )

    if shortfalls:
        print(
            f"\n⚠ {len(shortfalls)} scenario(s) below --per-label ({args.per_label}) in ≥1 stratum:",
            file=sys.stderr,
        )
        for s in shortfalls:
            print(f"    {s}", file=sys.stderr)
        print("  Loosen the cohort SQL filter(s) or lower --per-label. (exit 3)", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
