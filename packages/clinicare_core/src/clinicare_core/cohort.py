"""Read the gated cohort bundle: which patients are in the benchmark, and their gold labels.

The bundle is two files, distributed to PhysioNet-credentialed users and deliberately absent
from this repository (see DATA_ACCESS.md):

  full750.csv   task_id,scenario_id,params_json,expected_label   — the label source of truth
  dev148.csv    task_id                                          — frozen dev-subset membership

**Why `params_json` rather than columns.** The 25 scenarios declare eight different parameter
schemas, so a flat union would be mostly-empty columns in which "not a parameter for this
scenario" and "missing value" are indistinguishable.

**Why dev148 is membership only.** Labels are read live from full750, so an approved relabel
flows through while the *set* of 148 cases stays frozen. That set is a sample, not a
derivation — replaying the selection rule against revised labels does not reproduce it.

**Row order is load-bearing.** `build_tasks.py --per-label N` takes the first N rows per label
class per scenario, so the order rows appear in full750.csv defines which cases land in a
stratified subset. Readers here preserve file order; the writer must too.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

FULL = "full750.csv"
DEV = "dev148.csv"
FIELDS = ("task_id", "scenario_id", "params_json", "expected_label")


def cohort_dir(explicit: str | Path | None = None) -> Path:
    """The bundle directory, validated. Raises a RuntimeError that says how to get it."""
    raw = str(explicit) if explicit else os.environ.get("CLINICARE_COHORT_DIR", "").strip()
    if not raw:
        raise RuntimeError(
            "CLINICARE_COHORT_DIR is not set. The cohort bundle (full750.csv, dev148.csv) says "
            "which patients the benchmark covers and what their gold labels are. It is a MIMIC "
            "derivative, so it ships separately to PhysioNet-credentialed users rather than in "
            "this repository — see DATA_ACCESS.md."
        )
    d = Path(raw).expanduser()
    if not d.is_dir():
        raise RuntimeError(f"CLINICARE_COHORT_DIR does not exist or is not a directory: {d}")
    return d


def _require(path: Path) -> Path:
    if not path.is_file():
        raise RuntimeError(
            f"{path.name} not found at {path}. The cohort bundle should contain both "
            f"{FULL} and {DEV} — see DATA_ACCESS.md."
        )
    return path


def load_full(path: str | Path | None = None) -> list[dict]:
    """Every cohort row, in file order: {task_id, scenario_id, expected_label, **params}.

    Parameters are flattened out of params_json so callers can index a row by parameter name
    the way they would any cohort CSV.
    """
    p = Path(path) if path else _require(cohort_dir() / FULL)
    _require(p)
    out: list[dict] = []
    with p.open(newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in FIELDS if c not in (reader.fieldnames or [])]
        if missing:
            raise RuntimeError(f"{p} is missing column(s) {missing}; expected {list(FIELDS)}")
        for i, r in enumerate(reader, 2):  # 2 = first data line, for a useful error
            try:
                params = json.loads(r["params_json"])
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{p}:{i}: params_json is not valid JSON: {exc}") from exc
            out.append(
                {
                    "task_id": r["task_id"],
                    "scenario_id": r["scenario_id"],
                    "expected_label": (r["expected_label"] or "").strip(),
                    **{k: str(v) for k, v in params.items()},
                }
            )
    return out


def by_scenario(path: str | Path | None = None) -> dict[str, list[dict]]:
    """load_full() grouped by scenario id, each group keeping file order."""
    grouped: dict[str, list[dict]] = {}
    for row in load_full(path):
        grouped.setdefault(row["scenario_id"], []).append(row)
    return grouped


def load_dev(path: str | Path | None = None) -> list[str]:
    """The frozen dev-subset task ids, in file order."""
    p = Path(path) if path else _require(cohort_dir() / DEV)
    _require(p)
    with p.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if "task_id" not in (reader.fieldnames or []):
            raise RuntimeError(f"{p} has no task_id column")
        return [r["task_id"].strip() for r in reader if r.get("task_id", "").strip()]


def write_full(rows: list[dict], path: str | Path) -> int:
    """Write full750.csv from rows of {task_id, scenario_id, expected_label, params: dict}.

    `params` is written with its keys in the order given — the scenario's declared parameter
    order. That ordering is not cosmetic: task ids hash the parameter values joined in declared
    order, and two scenarios declare the same three parameters in different orders.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(FIELDS))
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "task_id": r["task_id"],
                    "scenario_id": r["scenario_id"],
                    "params_json": json.dumps(r["params"], separators=(",", ":")),
                    "expected_label": r["expected_label"],
                }
            )
    return len(rows)
