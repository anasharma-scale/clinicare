"""Rebuild the development subset with the frozen dev148 task set from the cohort bundle.

Why this exists. `build_tasks.py --per-label 2` picks the first 2 rows per expected_label class per
scenario, so editing any label reshuffles which patients land in the dev subset. Reclassifying a
single row from I-MA to NO is enough to swap one task id out of a scenario's dev slice and another
in — fine for the full pool, but it breaks per-task joins against dev job dirs from earlier runs.
This script rebuilds the pinned 148 ids instead, so the current dev set stays comparable.

    python3 benchmark/scripts/build_dev148.py --no-env-check

DO NOT REPLACE THIS WITH `--per-label 2`. Selecting by rule rather than by pin makes the dev set
a function of the current labels, so a future relabel silently redefines which 148 cases the
published numbers describe. The set is a SAMPLE, not a derivation.

Membership lives in the cohort bundle as dev148.csv (task ids only); labels and parameters come
from full750.csv in the same bundle, so an approved relabel flows through while the set stays
fixed. Expected shape: 148 ids across all 25 scenarios, at most two per scenario/class cell,
distribution YES 50 / NO 45 / I-LACK 39 / I-MA 14.

build_tasks.py is not modified. This writes a temporary cohort file holding only the pinned rows and
passes it as `--cohort <that file> --per-label 999`: any truthy --per-label routes output to the
suffixed dev directory, and 999 exceeds every scenario's row count so the stratified filter drops
nothing.
"""

import argparse
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from clinicare_core import load_dev, load_full, write_full

HERE = Path(__file__).resolve().parent
BENCHMARK = HERE.parent
ROOT = BENCHMARK.parent


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--no-env-check", action="store_true", help="passed through to build_tasks.py")
    # The policy-OFF ablation must run on the SAME pinned 148 tasks as policy-ON, or the contrast
    # stops being paired and task difficulty no longer cancels. Building it with a bare
    # `build_tasks.py --no-policy --per-label N` selects a different cohort and quietly breaks that.
    ap.add_argument(
        "--no-policy",
        action="store_true",
        help="policy-OFF ablation build (passed through to build_tasks.py); output "
        "lands in tasks_dev_nopolicy/ instead of tasks_dev_policy/",
    )
    ap.add_argument("--workers", type=int, help="passed through to build_tasks.py")
    ap.add_argument("--cohort", help="bundle full750.csv (default: $CLINICARE_COHORT_DIR)")
    ap.add_argument("--pin", help="bundle dev148.csv (default: $CLINICARE_COHORT_DIR)")
    args = ap.parse_args()

    ids = load_dev(args.pin)
    rows = load_full(args.cohort)
    by_id = {r["task_id"]: r for r in rows}

    missing = [t for t in ids if t not in by_id]
    if missing:
        sys.exit(
            f"{len(missing)} pinned task id(s) are not in the cohort — a pinned patient was "
            f"removed or its params changed: {missing[:5]}"
        )

    # Emit the pinned rows in cohort order (not pin order) so the build sees the same ordering
    # a full build would; --per-label 999 keeps everything, so only grouping matters.
    pinned = [r for r in rows if r["task_id"] in set(ids)]
    scenario_params = {}
    for r in pinned:
        scenario_params.setdefault(
            r["scenario_id"],
            [k for k in r if k not in ("task_id", "scenario_id", "expected_label")],
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="dev148_"))
    cohort_file = tmpdir / "full750.csv"  # name matters only to the loader's error messages
    try:
        write_full(
            [
                {
                    "task_id": r["task_id"],
                    "scenario_id": r["scenario_id"],
                    "expected_label": r["expected_label"],
                    "params": {k: r[k] for k in scenario_params[r["scenario_id"]]},
                }
                for r in pinned
            ],
            cohort_file,
        )
        print(f"pinned {len(pinned)} tasks across {len(scenario_params)} scenarios")

        cmd = [
            sys.executable,
            str(HERE / "build_tasks.py"),
            "--cohort",
            str(cohort_file),
            "--per-label",
            "999",
        ]
        if args.no_policy:
            cmd.append("--no-policy")
        if args.no_env_check:
            cmd.append("--no-env-check")
        if args.workers:
            cmd += ["--workers", str(args.workers)]
        print("+", " ".join(cmd))
        rc = subprocess.call(cmd, cwd=ROOT)
        if rc != 0:
            sys.exit(f"build_tasks.py exited {rc}")
    finally:
        cohort_file.unlink(missing_ok=True)
        tmpdir.rmdir()

    # DERIVE the output dir from the flags we passed, never SEARCH for it: a search can pick stale
    # output from an earlier build over what this run just wrote, and then report success.
    # Mirrors build_tasks.py's own composition (`f"{base}_dev{dev_suffix}"`); a rename there breaks
    # the check below.
    out_dir = BENCHMARK / ("tasks_dev_nopolicy" if args.no_policy else "tasks_dev_policy")
    if not out_dir.is_dir():
        sys.exit(
            f"expected build output at {out_dir} but it does not exist -- build_tasks.py's output "
            "naming has diverged from this derivation; re-check its `out_dir = ...` line"
        )
    built = {p.name for p in out_dir.iterdir() if (p / "task.toml").exists()}
    print(f"\n{out_dir.name}: built {len(built)}, pinned {len(ids)}")
    if built != set(ids):
        print(
            f"  MISMATCH missing={sorted(set(ids) - built)[:5]} extra={sorted(built - set(ids))[:5]}"
        )
        sys.exit(1)
    print("  membership matches the pin \u2713")
    dist = Counter(by_id[t]["expected_label"].replace("INDETERMINATE_", "I-") for t in ids)
    print("  labels:", dict(sorted(dist.items())))


if __name__ == "__main__":
    main()
