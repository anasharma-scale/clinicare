"""Task-id scheme, shared by build_tasks.py (generates task dirs) and analyze_labels.py
(maps trials back to their cohort row). Keep it here so the two never drift.

A task id is `<scenario_id>-<hash>`, where the hash is derived from the case's param values
(e.g. subject_id + hadm_id). So the SAME patient always yields the SAME task id — regardless
of which cohort CSV it came from or its row position — instead of a positional `-<NNN>` that
would mean different patients across different CSVs.

HASH_LEN is hex chars: 16^6 ≈ 16.8M, so collisions are negligible at cohort scale (a few
hundred rows/scenario). build_tasks.py still hard-checks for a collision within a scenario and errors
if one ever occurs, so shortening this can never silently mislabel — worst case is a loud
"increase HASH_LEN" at build time.
"""

from __future__ import annotations

import hashlib

HASH_LEN = 6


def param_key(params: list[str], row: dict) -> str:
    """Stable string for a cohort row's identity: its param values in declared order."""
    return "|".join(str(row[p]).strip() for p in params)


def param_hash(params: list[str], row: dict) -> str:
    return hashlib.sha256(param_key(params, row).encode()).hexdigest()[:HASH_LEN]


def task_id(scenario_id: str, params: list[str], row: dict) -> str:
    return f"{scenario_id}-{param_hash(params, row)}"
