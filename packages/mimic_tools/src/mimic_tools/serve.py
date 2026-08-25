"""Sidecar entrypoint: the credentialed data service the agent's proxy shim talks to.

This is the ONLY process in a trial with access to MIMIC. It serves the canonical tool surface
over HTTP (api.py).
The agent runs in a separate container with no creds and no data egress, reaching these tools
only through `mcp_server.py` in proxy mode (MIMIC_TOOLS_URL) — see SIDECAR.md.

Run (MIMIC_API_SECRET is required by default — it will refuse to start without one; add
MIMIC_TOOLS_HOST=0.0.0.0 only when the agent lives in another container/host):
    # DuckDB backend: reads the local Parquet tree at MIMIC_DATA_ROOT
    MIMIC_BACKEND=duckdb MIMIC_API_SECRET=... python -m mimic_tools.serve

    # BigQuery backend: credentials come from ADC (or a forwarded per-request token)
    MIMIC_BACKEND=bigquery MIMIC_API_SECRET=... python -m mimic_tools.serve

Env:
    MIMIC_TOOLS_HOST   bind host   (default 127.0.0.1; set 0.0.0.0 to be reachable from
                       another container — the trial compose file already does)
    MIMIC_TOOLS_PORT   bind port   (default 8799)
    MIMIC_API_SECRET / MIMIC_REQUIRE_API_SECRET  shared x-api-key auth (see api.py)
    MIMIC_POLICY_TOOLS + POLICY_CORPUS_DIR       to serve the policy tools from here
    plus backend selection (MIMIC_BACKEND, and MIMIC_DATA_ROOT for DuckDB).
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    from . import db

    # Fail fast on an unreadable dataset: preflight one cheap read BEFORE
    # serving, and refuse to start (exit 3) if it fails. On docker, `docker compose up --wait`
    # then fails the trial in seconds instead of the sidecar coming up "healthy" and every tool
    # call degrading into silent "Indeterminate – lack of data". It lives here, not in the agent,
    # because the sidecar is the only process with the creds. No-op on BigQuery (per-request
    # identity; preflight returns immediately).
    try:
        db.preflight()
    except Exception as exc:  # noqa: BLE001
        print(
            f"[mimic-serve] FATAL: MIMIC data preflight failed — {exc}\n"
            "[mimic-serve] refusing to start so the trial errors now instead of hedging to "
            "'lack of data'. Fix the data configuration (see DATA_ACCESS.md) and re-run.",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(3) from exc

    import uvicorn

    uvicorn.run(
        "mimic_tools.api:app",
        # Loopback by DEFAULT. The compose file that runs the supported Docker path sets
        # 0.0.0.0 explicitly (sidecar.compose.yml), where it is correct — that is a private
        # trial network. A hand-rolled `python -m mimic_tools.serve` on a cloud VM is the case
        # that must not bind every interface by accident: with a permissive security group
        # that publishes a credentialed MIMIC query endpoint to the internet. Binding wide is
        # now a choice the operator makes, not a default they inherit.
        host=os.environ.get("MIMIC_TOOLS_HOST", "127.0.0.1"),
        port=int(os.environ.get("MIMIC_TOOLS_PORT", "8799")),
        log_level=os.environ.get("MIMIC_TOOLS_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
