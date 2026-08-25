"""Step 5+6 of the label pipeline: consensus selection → the cohort bundle's `full750.csv`.

Position in the full pipeline:

    select_cohort.py            # 1-2. cohort.sql → silver_patients.csv (balanced sampling pool)
    build_tasks.py --include-answer   # 3. render tasks_answer/ (prompt + oracle reference spec)
    harbor run -c configs/oracle_*.yaml   # 4. run the 3 oracle models over tasks_answer/
    analyze_labels.py           #    → label_agreement.csv (per-model verdicts + consensus)
    finalize_cohort.py          # 5-6. THIS: pick a balanced N/scenario by consensus → full750.csv
                                #       (see ../README.md "Label lifecycle")

What it does, per scenario, reading `label_agreement.csv`:
  5. SELECT a balanced cohort by the model-consensus label, preferring high agreement:
       - rank agreement unanimous > majority > split; shuffle (seed 42) then stable-sort by rank,
         so ties break deterministically and the highest-consensus tasks are taken first;
       - drop SPLIT-consensus tasks (no agreed label — see caveat below);
       - target NUM_YES_NO (YES+NO, split evenly) + NUM_INDETERMINATE (the two indeterminate
         subtypes, split evenly) = the per-scenario cohort size, with `allocate_samples` back-filling
         from the sibling class when one is under-populated (so a scenario short on NO still fills to
         target from YES, etc.).
  6. WRITE the selection as one `full750.csv` in the cohort bundle dir ($CLINICARE_COHORT_DIR, or
     --out): `task_id`, `scenario_id`, `params_json` and `expected_label` (= the consensus). Task
     ids hash each row's params in the order its scenario.toml declares them.

This does not fully reproduce the released labels: the split cases in the cohort bundle were
hand-adjudicated by physicians, which no script can regenerate. Runs DRY by default — prints the
selection, writing nothing. `--write` emits the CSV, overwriting any bundle already there, so use
it only on a fresh regeneration where you mean to discard what exists.
"""

from __future__ import annotations

import argparse
import csv
import random
import tomllib
from collections import Counter
from pathlib import Path

from clinicare_core import cohort_dir, task_id, write_full

SCRIPTS = Path(__file__).resolve().parent  # construction/scripts/
CONSTRUCTION = SCRIPTS.parent  # construction/
ROOT = CONSTRUCTION.parent  # repo root
SCENARIOS_DIR = ROOT / "benchmark" / "_scenarios"

# Per-scenario target shape: 10 YES / 10 NO / 5 ILD / 5 IMA = 30. Back-fill covers under-populated classes.
NUM_YES_NO = 20
NUM_INDETERMINATE = 10
AGREEMENT_RANK = {"unanimous": 3, "majority": 2, "split": 1}
SEED = 42

YES, NO = "YES", "NO"
ILD, IMA = "INDETERMINATE_LACK_OF_DATA", "INDETERMINATE_MEDICAL_AMBIGUITY"


def allocate_samples(len1: int, len2: int, target1: int, target2: int) -> tuple[int, int]:
    """Split `target1 + target2` picks across two classes, back-filling from the sibling when one is
    short. Raises if the combined pool can't meet the total."""
    total = target1 + target2
    if len1 + len2 < total:
        raise ValueError(f"cannot allocate {total} from pools of {len1} and {len2}")
    if len2 < target2:
        return total - len2, len2
    if len1 < target1:
        return len1, total - len1
    return target1, target2


def select_scenario(rows: list[dict]) -> list[dict]:
    """The balanced, high-agreement-first selection for one scenario's rows from label_agreement.csv."""
    ordered = rows[:]
    random.Random(SEED).shuffle(ordered)
    ordered.sort(key=lambda r: AGREEMENT_RANK.get(r.get("agreement", ""), 0), reverse=True)

    by_label: dict[str, list[dict]] = {}
    for r in ordered:
        by_label.setdefault(r["consensus"], []).append(r)
    yes, no = by_label.get(YES, []), by_label.get(NO, [])
    ild, ima = by_label.get(ILD, []), by_label.get(IMA, [])

    sel_yn, sel_ind = allocate_samples(
        len(yes) + len(no), len(ild) + len(ima), NUM_YES_NO, NUM_INDETERMINATE
    )
    n_yes = sel_yn // 2
    sel_yes, sel_no = allocate_samples(len(yes), len(no), n_yes, sel_yn - n_yes)
    n_ild = sel_ind // 2
    sel_ild, sel_ima = allocate_samples(len(ild), len(ima), n_ild, sel_ind - n_ild)

    return yes[:sel_yes] + no[:sel_no] + ild[:sel_ild] + ima[:sel_ima]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--input",
        default=str(CONSTRUCTION / "label_agreement.csv"),
        help="analyze_labels.py output (default: construction/label_agreement.csv)",
    )
    ap.add_argument("--out", help="output full750.csv (default: $CLINICARE_COHORT_DIR)")
    ap.add_argument(
        "--write",
        action="store_true",
        help="emit full750.csv (default: dry-run). OVERWRITES hand-adjudicated labels.",
    )
    args = ap.parse_args()

    scenarios = {}
    bundle_rows: list[dict] = []
    for d in sorted(SCENARIOS_DIR.iterdir()):
        toml = d / "scenario.toml"
        if toml.exists():
            c = tomllib.loads(toml.read_text())
            scenarios[c["id"]] = (d, c["params"])

    by_scenario: dict[str, list[dict]] = {}
    with open(args.input, newline="") as f:
        for r in csv.DictReader(f):
            # `case` is the pre-rename column name; a label_agreement.csv produced before the
            # rename is still readable, so an existing run's labels can be re-finalized.
            by_scenario.setdefault(r.get("scenario") or r["case"], []).append(r)

    unknown = set(by_scenario) - set(scenarios)
    if unknown:
        raise SystemExit(
            f"{Path(args.input).name} has scenario id(s) with no _scenarios/ dir: {sorted(unknown)}"
        )

    if not args.write:
        print("DRY RUN (pass --write to emit full750.csv). Selection per scenario:\n")

    for cid, (d, params) in scenarios.items():
        rows = by_scenario.get(cid, [])
        try:
            selected = select_scenario(rows)
        except ValueError as e:
            print(f"{cid:24} SKIP — {e}")
            continue
        dist = Counter(r["consensus"] for r in selected)
        dist_str = " ".join(
            f"{k.split('_')[-1] if k.startswith('INDETERM') else k}={dist[k]}"
            for k in (YES, NO, ILD, IMA)
            if dist[k]
        )

        # Params in the scenario's DECLARED order — task ids hash them in that order, and two
        # scenarios declare the same three params differently, so a canonical order would
        # renumber their tasks.
        bundle_rows.extend(
            {
                "task_id": task_id(cid, params, r),
                "scenario_id": cid,
                "expected_label": r["consensus"],
                "params": {p: str(r[p]).strip() for p in params},
            }
            for r in selected
        )
        print(f"{cid:24} select {len(selected):2d}  {dist_str}")

    if args.write:
        out = Path(args.out) if args.out else (cohort_dir() / "full750.csv")
        n = write_full(bundle_rows, out)
        print(f"\nwrote {n} rows -> {out}")
    else:
        print(f"\nDRY RUN ({len(bundle_rows)} rows selected; pass --write to emit full750.csv).")
        print(
            "Note: differences vs the released cohort bundle are expected — it includes "
            "physician split-case adjudications this script does not reproduce."
        )


if __name__ == "__main__":
    main()
