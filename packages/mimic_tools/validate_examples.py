"""Validate the per-tool `example` param sets declared in tool_registry.py against a
live backend — proof that every example a contributor can "load" actually returns data.

Mirrors smoke_test.py, but instead of bootstrapping ids it exercises the EXACT examples
the UIs surface, so a stale id or a renamed param is caught here, not by a confused CB.

Run:
    MIMIC_DATA_ROOT=/path/to/mimic-parquet uv run python validate_examples.py

Exit code is non-zero if any example errors or comes back empty, so it can gate CI.
Manual tools (no `fn`) are listed but not executed — they're contributor-run.
"""

from __future__ import annotations

import sys

from mimic_tools.tool_registry import MANUAL_TOOLS, TOOLS, coerce_params


def _nonempty(result) -> bool:
    """Did the example return real data? Empty list / None / 0-row run_sql = suspicious."""
    if result is None:
        return False
    if isinstance(result, list):
        return len(result) > 0
    if isinstance(result, dict):
        if "rows" in result and "columns" in result:  # run_sql
            return bool(result.get("rows"))
        return len(result) > 0
    return True


def _actual_keys(result) -> set:
    """Top-level field names the result actually carries (row keys for a table)."""
    if isinstance(result, list):
        return set(result[0].keys()) if result else set()
    if isinstance(result, dict):
        return set(result.keys())
    return set()


def main() -> int:
    failures: list[str] = []
    print("=== validating tool examples ===\n")
    for name, spec in TOOLS.items():
        example = spec.get("example")
        if example is None:
            failures.append(f"{name}: no example declared")
            print(f"  [MISSING] {name}: no example")
            continue
        kwargs, err = coerce_params(spec, example)
        if err:
            failures.append(f"{name}: bad example params — {err}")
            print(f"  [BADPARAM] {name}: {err}")
            continue
        try:
            result = spec["fn"](**kwargs)
        except Exception as exc:  # noqa: BLE001 — report every failure, don't abort the run
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"  [ERROR]    {name}({example}) -> {type(exc).__name__}: {exc}")
            continue
        if not _nonempty(result):
            failures.append(f"{name}: example returned EMPTY")
            print(f"  [EMPTY]    {name}({example}) -> no data")
            continue
        # Output-schema check: declared output.fields names vs the actual returned keys.
        declared = {f["name"] for f in (spec.get("output") or {}).get("fields", [])}
        actual = _actual_keys(result)
        missing, extra = sorted(declared - actual), sorted(actual - declared)
        n = len(result) if isinstance(result, (list, dict)) else 1
        if not declared:
            failures.append(f"{name}: no output schema declared")
            print(f"  [NO-OUT]   {name} -> {n}; no output schema")
        elif missing or extra:
            failures.append(f"{name}: output schema drift — missing={missing} extra={extra}")
            print(f"  [DRIFT]    {name} -> missing={missing} extra={extra}")
        else:
            print(f"  [ok]       {name} -> {n}; output schema matches ({len(declared)} fields)")

    print("\n=== manual tools (not executed; example presence only) ===")
    for name, spec in MANUAL_TOOLS.items():
        ok = "ok" if spec.get("example") else "MISSING"
        print(f"  [{ok}] {name}")
        if not spec.get("example"):
            failures.append(f"{name}: no example declared")

    print()
    if failures:
        print(f"FAILED: {len(failures)} issue(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All examples returned data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
