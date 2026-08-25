"""Trajectory persistence for the tool console.

One JSONL object per (task_id, contributor, session), written under TRAJECTORY_DIR (default
./.trajectories). The file is REWRITTEN on each save so load-bearing toggles stay in sync; this
backend is stateless and the frontend owns the transcript, re-sending the full ordered list.

Env:
  TRAJECTORY_DIR   output directory (default ./.trajectories)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

TRAJECTORY_DIR = os.environ.get("TRAJECTORY_DIR", os.path.join(os.getcwd(), ".trajectories"))


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", (s or "").strip()) or "none"


def fingerprint(result: Any) -> dict:
    """Compact result summary for the log (not the full payload). Mirrors app.py."""
    if result is None:
        return {"type": "none"}
    if isinstance(result, list):
        return {
            "type": "list",
            "rows": len(result),
            "keys": list(result[0].keys()) if result else [],
        }
    if isinstance(result, dict):
        if "rows" in result and "columns" in result:
            return {
                "type": "sql",
                "returned": result.get("returned"),
                "truncated": result.get("truncated"),
            }
        return {"type": "dict", "keys": list(result.keys())}
    return {"type": type(result).__name__}


def filename(task_id: str, contributor: str, session_token: str) -> str:
    """The JSONL name for one (task, contributor, session) — public so a frontend can
    show where it is logging without recomputing the convention."""
    return f"{slug(task_id)}__{slug(contributor)}__{slug(session_token)}.jsonl"


def _render(task_id: str, contributor: str, records: list[dict]) -> str:
    """Serialize the transcript to JSONL with the same per-line shape as app.py."""
    lines: list[str] = []
    for rec in records:
        res = rec.get("result")
        manual = bool(rec.get("manual"))
        # Manual-tool outputs (the contributor's own Python output / web findings) aren't
        # reproducible by re-running, so store them verbatim. Data-tool results ARE
        # reproducible -> keep just a compact fingerprint (or pass a precomputed one through).
        if manual:
            result = res
        elif isinstance(res, dict) and "type" in res:
            result = res
        else:
            result = fingerprint(res)
        lines.append(
            json.dumps(
                {
                    "seq": rec.get("seq"),
                    "ts": rec.get("ts"),
                    "task_id": task_id,
                    "contributor": contributor,
                    "tool": rec.get("tool"),
                    "params": rec.get("params"),
                    "ok": rec.get("ok"),
                    "error": rec.get("error"),
                    "load_bearing": rec.get("load_bearing", False),
                    "manual": manual,
                    "result": result,
                },
                default=str,
            )
        )
    return ("\n".join(lines) + "\n") if lines else ""


def persist(task_id: str, contributor: str, session_token: str, records: list[dict]) -> str:
    """Write the full transcript as one JSONL object. Returns the location written."""
    body = _render(task_id, contributor, records)
    fname = filename(task_id, contributor, session_token)
    os.makedirs(TRAJECTORY_DIR, exist_ok=True)
    path = os.path.join(TRAJECTORY_DIR, fname)
    with open(path, "w") as f:
        f.write(body)
    return path
