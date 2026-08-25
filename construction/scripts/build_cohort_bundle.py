"""Assemble the gated cohort bundle (full750.csv + dev148.csv) from per-scenario cohort CSVs.

    python construction/scripts/build_cohort_bundle.py \\
        --scenarios <dir of scenario-NN-*/patients.csv> --pin <dev148_pin.csv> --dst <bundle dir>

The bundle is the only artifact carrying patient identifiers and gold labels, so it is
distributed to PhysioNet-credentialed users rather than committed here (DATA_ACCESS.md).
This merges the 25 per-scenario `patients.csv` into one `full750.csv`, and converts the frozen
dev-subset pin into a membership-only `dev148.csv`.

TASK IDS ARE RECOMPUTED AND CHECKED, NOT COPIED. A task id is a hash of the cohort row's
parameter values joined **in the order the scenario declares them** — and two scenarios declare
the same three parameters in different orders. So a merge that canonicalised parameter order
would silently renumber those scenarios' tasks and quietly invalidate every published result
keyed by task id. Every id is regenerated from scenario.toml's declared `params` and compared
against the input; any mismatch aborts the whole run.

Row order is preserved per scenario, because `build_tasks.py --per-label N` takes the first N
rows per label class — the order in full750.csv defines which cases a stratified subset picks.
"""

from __future__ import annotations

import argparse
import csv
import sys
import tomllib
from collections import Counter
from pathlib import Path

from clinicare_core import load_dev, task_id, write_full

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_SCENARIOS = ROOT / "benchmark" / "_scenarios"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--scenarios",
        type=Path,
        default=DEFAULT_SCENARIOS,
        help="dir of scenario-NN-*/ holding scenario.toml and the cohort CSV "
        f"(default: {DEFAULT_SCENARIOS})",
    )
    ap.add_argument("--csv-name", default="patients.csv", help="cohort CSV per scenario dir")
    ap.add_argument("--pin", type=Path, help="dev148_pin.csv; omit to skip dev148.csv")
    ap.add_argument("--dst", type=Path, required=True, help="output bundle directory")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    if not args.scenarios.is_dir():
        sys.exit(f"--scenarios is not a directory: {args.scenarios}")

    rows: list[dict] = []
    mismatches: list[str] = []
    per_scenario: list[tuple[str, int]] = []

    for d in sorted(args.scenarios.iterdir()):
        toml = d / "scenario.toml"
        cohort = d / args.csv_name
        if not toml.is_file():
            continue
        if not cohort.is_file():
            print(f"  {d.name}: no {args.csv_name} — skipping", file=sys.stderr)
            continue
        scenario = tomllib.loads(toml.read_text())
        sid, params = scenario["id"], scenario["params"]

        with cohort.open(newline="") as fh:
            src_rows = list(csv.DictReader(fh))
        if not src_rows:
            print(f"  {d.name}: {args.csv_name} is empty — skipping", file=sys.stderr)
            continue
        missing = [p for p in params if p not in src_rows[0]]
        if missing:
            sys.exit(f"{d.name}/{args.csv_name} lacks column(s) for declared params: {missing}")

        for i, r in enumerate(src_rows, 2):
            # Declared order, not CSV column order — this is the whole point (see docstring).
            ordered = {p: str(r[p]).strip() for p in params}
            tid = task_id(sid, params, ordered)
            if "task_id" in r and r["task_id"].strip() and r["task_id"].strip() != tid:
                mismatches.append(f"{d.name}:{i} {r['task_id'].strip()} != {tid}")
            rows.append(
                {
                    "task_id": tid,
                    "scenario_id": sid,
                    "expected_label": (r.get("expected_label") or "").strip(),
                    "params": ordered,
                }
            )
        per_scenario.append((sid, len(src_rows)))

    if mismatches:
        sys.exit(
            f"{len(mismatches)} task id(s) do not reproduce from scenario.toml's declared param "
            f"order:\n  " + "\n  ".join(mismatches[:10]) + "\nRefusing to write a bundle that "
            "would renumber tasks."
        )

    dupes = [t for t, n in Counter(r["task_id"] for r in rows).items() if n > 1]
    if dupes:
        sys.exit(f"duplicate task id(s) across the cohort: {dupes[:10]}")

    dev_ids: list[str] = []
    if args.pin:
        if not args.pin.is_file():
            sys.exit(f"--pin not found: {args.pin}")
        with args.pin.open(newline="") as fh:
            dev_ids = [r["task_id"].strip() for r in csv.DictReader(fh) if r.get("task_id")]
        known = {r["task_id"] for r in rows}
        orphans = [t for t in dev_ids if t not in known]
        if orphans:
            sys.exit(
                f"{len(orphans)} pinned dev id(s) are not in the cohort — the pin and the "
                f"cohort have diverged: {orphans[:5]}"
            )

    labels = Counter(r["expected_label"] for r in rows)
    print(f"\n{len(rows)} rows across {len(per_scenario)} scenarios")
    print("  labels:", dict(sorted(labels.items())))
    if dev_ids:
        print(f"  dev subset: {len(dev_ids)} task ids, all present in the cohort")
    if args.dry_run:
        print("\n(dry run — nothing written)")
        return

    args.dst.mkdir(parents=True, exist_ok=True)
    n = write_full(rows, args.dst / "full750.csv")
    print(f"\nwrote {n} rows -> {args.dst / 'full750.csv'}")
    if dev_ids:
        p = args.dst / "dev148.csv"
        with p.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["task_id"])
            w.writerows([[t] for t in dev_ids])
        print(f"wrote {len(dev_ids)} task ids -> {p}")

    # Read the bundle back through the same loader the benchmark uses, so a format mistake
    # surfaces here rather than at someone else's first build_tasks.py run.
    from clinicare_core import load_full

    back = load_full(args.dst / "full750.csv")
    assert len(back) == len(rows), f"round-trip lost rows: {len(back)} != {len(rows)}"
    for a, b in zip(rows, back):
        assert (
            a["task_id"] == b["task_id"]
        ), f"round-trip reordered: {a['task_id']} vs {b['task_id']}"
        for k, v in a["params"].items():
            assert b[k] == v, f"round-trip changed {a['task_id']}.{k}: {v!r} -> {b[k]!r}"
    if dev_ids:
        assert load_dev(args.dst / "dev148.csv") == dev_ids, "dev148 round-trip mismatch"
    print("round-trip verified through clinicare_core.cohort")
    print(f"\nSet CLINICARE_COHORT_DIR={args.dst}")


if __name__ == "__main__":
    main()
