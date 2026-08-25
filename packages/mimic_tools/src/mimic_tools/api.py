"""FastAPI wrapper exposing the canonical MIMIC tool surface (tools.py) over HTTP.

This is what the credential-isolated sidecar runs (`python -m mimic_tools.serve`): the one
process in a trial that can reach MIMIC. The agent talks to it through mcp_server.py in proxy
mode and holds no data credentials of its own. See SIDECAR.md.

Endpoints:
  GET  /healthz       liveness
  GET  /tools         tool catalog (drives generic form rendering in the UI)
  GET  /options       distinct values for a controlled-vocab dropdown (enum_dynamic)
  GET  /schema        logical-table schema (run_sql reference)
  POST /call-tool     execute one tool, return result + fingerprint
  POST /trajectory    persist the full ordered transcript (mirrors the Streamlit log)

Auth / identity:
  - Shared secret between the agent's proxy shim and this service via the `x-api-key`
    header (MIMIC_API_SECRET). Required by DEFAULT: the app refuses to start without it, so
    an unset secret can never silently leave the service open (the check is
    `if secret and ...`, so no secret means no auth). Every endpoint but /healthz gates on
    it. Opt out for an isolated local instance with MIMIC_REQUIRE_API_SECRET=0.
  - Optional per-request BigQuery identity via headers (headers, not the body, so tokens
    stay out of request-body logs):
        X-BigQuery-Access-Token:    the caller's OAuth access token
        X-BigQuery-Billing-Project: the caller's GCP project for query billing
    Only required when MIMIC_BQ_PER_REQUEST_AUTH=1, i.e. a multi-tenant deployment; a
    self-hosted sidecar uses its own credentials.

Run locally (from the project root; needs `uv sync --extra api`). MIMIC_API_SECRET is
required by default; MIMIC_REQUIRE_API_SECRET=0 opts a local-only instance out:
  DuckDB (needs MIMIC_DATA_ROOT for tool calls; /healthz + /tools need nothing):
    MIMIC_DATA_ROOT=/path/to/mimic-parquet MIMIC_REQUIRE_API_SECRET=0 \
        uv run uvicorn mimic_tools.api:app --reload --port 8000
  BigQuery:
    MIMIC_BACKEND=bigquery MIMIC_REQUIRE_API_SECRET=0 \
        uv run uvicorn mimic_tools.api:app --port 8000
  Interactive API docs: http://localhost:8000/docs
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import db, tools, trajectory
from .tool_registry import MANUAL_TOOLS, TOOLS, coerce_params


def _require_api_secret_enabled() -> bool:
    """Whether a missing MIMIC_API_SECRET should refuse to start. Defaults to YES.

    The default is on because the failure is silent and the blast radius is patient data: the
    auth check below is `if secret and ...`, so an unset secret disables auth for every
    endpoint, and serve.py binds a port. An operator self-hosting the sidecar (what a
    non-Docker Harbor backend such as Modal requires) who never read SIDECAR.md would
    otherwise stand up an open MIMIC-IV query endpoint and get no signal that they had.
    Opting out is deliberate and explicit: MIMIC_REQUIRE_API_SECRET=0.
    """
    return os.environ.get("MIMIC_REQUIRE_API_SECRET", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


if _require_api_secret_enabled() and not os.environ.get("MIMIC_API_SECRET"):
    raise RuntimeError(
        "MIMIC_API_SECRET is not set. Refusing to start an unauthenticated, writable service "
        "over credentialed MIMIC data. Generate one (`openssl rand -hex 32`) and pass it to "
        "both this service and the agent's proxy shim — see SIDECAR.md. For a genuinely "
        "isolated local instance you can set MIMIC_REQUIRE_API_SECRET=0 to opt out."
    )

app = FastAPI(title="MIMIC-IV Tool API", version="0.1.0")

# (column, table) pairs /options is allowed to query. Built from the enum_dynamic
# params declared in the registry — NOT from caller input. These names are
# interpolated into SQL unparameterized, so they must come from a fixed allowlist.
_OPTION_SOURCES: set[tuple[str, str]] = {
    tuple(p["source"])
    for spec in TOOLS.values()
    for p in spec["params"]
    if p["kind"] == "enum_dynamic"
}


def _require_secret(x_api_key: str | None = Header(default=None)) -> None:
    secret = os.environ.get("MIMIC_API_SECRET")
    if secret and x_api_key != secret:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _is_bq_auth_error(exc: BaseException) -> bool:
    """True if the exception looks like a rejected/expired BigQuery OAuth token, so we can
    surface a clear 'refresh your token' message instead of a raw google RefreshError."""
    if type(exc).__name__ in ("RefreshError", "Unauthorized", "Unauthenticated"):
        return True
    s = str(exc).lower()
    return (
        "401" in s
        or "unauthor" in s
        or "invalid authentication" in s
        or "invalid credential" in s
        or "invalid_grant" in s
        or "do not contain the necessary fields" in s
        or ("token" in s and ("expired" in s or "invalid" in s))
    )


@contextlib.contextmanager
def _bq_context(access_token: str | None, billing_project: str | None):
    """Scope a caller's BigQuery identity to this request; a no-op on the DuckDB backend.

    Per-request token forwarding (MIMIC_BQ_PER_REQUEST_AUTH=1) is for a MULTI-TENANT
    deployment, where each caller must query under their own credentialed PhysioNet identity.
    It is OFF by default, because it is also the only thing here with a one-hour ceiling: the
    forwarded value is a bare access token carrying no refresh material, so it expires mid-run
    after 60 minutes and takes long sweeps down with it. A self-hosted single-user sidecar —
    the normal case — falls through to Application Default Credentials, which hold a refresh
    token and renew themselves for as long as the run lasts."""
    if db.BACKEND == "bigquery":
        require_token = os.environ.get("MIMIC_BQ_PER_REQUEST_AUTH", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if require_token and not access_token:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Missing X-BigQuery-Access-Token. This sidecar runs with "
                    "MIMIC_BQ_PER_REQUEST_AUTH=1, so every call must carry the caller's own "
                    "PhysioNet-linked Google OAuth token. Unset that variable to use the "
                    "sidecar's own Application Default Credentials instead."
                ),
            )
        try:
            if access_token:
                with db.bq_credentials(access_token, billing_project):
                    yield
            else:
                yield  # no forwarded identity -> db falls through to ADC
        except HTTPException:
            raise
        except Exception as exc:
            # Auth failure surfaces deep inside the query as a google RefreshError. Translate it
            # so every endpoint (call-tool/options/schema) returns something actionable, and say
            # which credential actually failed — the fix differs.
            if _is_bq_auth_error(exc):
                fix = (
                    "refresh the forwarded token (`gcloud auth print-access-token`) — note a "
                    "forwarded access token has no refresh material and dies after ~1 hour"
                    if access_token
                    else "re-run `gcloud auth application-default login` on the sidecar host"
                )
                raise HTTPException(
                    status_code=401, detail=f"BigQuery credentials rejected or expired — {fix}."
                ) from exc
            raise
    else:
        yield


def _catalog() -> list[dict]:
    """Serializable catalog: executed data tools + log-only manual tools (flagged)."""

    def entries(src: dict, manual: bool) -> list[dict]:
        return [
            {
                "name": name,
                "doc": spec["doc"],
                "group": spec.get("group"),
                "tables": spec.get("tables", []),
                "output": spec.get("output"),
                "example": spec.get("example"),
                "params": [{k: v for k, v in p.items()} for p in spec["params"]],
                "manual": manual,
            }
            for name, spec in src.items()
        ]

    return entries(TOOLS, False) + entries(MANUAL_TOOLS, True)


# ------------------------------- request models -------------------------------- #


class CallToolRequest(BaseModel):
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class CallToolResponse(BaseModel):
    ok: bool
    result: Any = None
    fingerprint: dict | None = None
    error: str | None = None


class TrajectoryRecord(BaseModel):
    seq: int
    ts: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    ok: bool = True
    error: str | None = None
    load_bearing: bool = False
    manual: bool = False
    # The fingerprint from /call-tool (preferred) or a raw result; persist() handles both.
    # For manual tools this is the contributor's own output/finding, stored verbatim.
    result: Any = None


class TrajectoryRequest(BaseModel):
    task_id: str
    contributor: str
    session_token: str
    records: list[TrajectoryRecord] = Field(default_factory=list)


# ------------------------------- endpoints ------------------------------------- #


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "backend": db.BACKEND}


@app.get("/tools", dependencies=[Depends(_require_secret)])
def list_tools() -> dict:
    return {"backend": db.BACKEND, "tools": _catalog()}


@app.get("/options", dependencies=[Depends(_require_secret)])
def options(
    column: str,
    table: str,
    x_bigquery_access_token: str | None = Header(default=None),
    x_bigquery_billing_project: str | None = Header(default=None),
) -> dict:
    if (column, table) not in _OPTION_SOURCES:
        raise HTTPException(status_code=400, detail=f"Unknown option source: {table}.{column}")
    with _bq_context(x_bigquery_access_token, x_bigquery_billing_project):
        res = tools.run_sql(
            f"SELECT DISTINCT {column} AS v FROM {table} WHERE {column} IS NOT NULL ORDER BY v",
            max_rows=500,
        )
    return {"options": [""] + [r["v"] for r in res["rows"]]}


@app.get("/schema", dependencies=[Depends(_require_secret)])
def schema(
    x_bigquery_access_token: str | None = Header(default=None),
    x_bigquery_billing_project: str | None = Header(default=None),
) -> dict:
    with _bq_context(x_bigquery_access_token, x_bigquery_billing_project):
        cols = db.schema()  # {table: [{name, type, description}]}
    return {
        "backend": db.BACKEND,
        # Back-compat: existing frontends read `tables` as {table: [column_name]}. Keep it
        # so a backend-only redeploy doesn't break a not-yet-updated client.
        "tables": {t: [c["name"] for c in v] for t, v in cols.items()},
        # Enriched: types + descriptions for clients that render them (the Tables view).
        "columns": cols,
    }


@app.post("/call-tool", dependencies=[Depends(_require_secret)], response_model=CallToolResponse)
def call_tool(
    req: CallToolRequest,
    x_bigquery_access_token: str | None = Header(default=None),
    x_bigquery_billing_project: str | None = Header(default=None),
) -> CallToolResponse:
    if req.tool in MANUAL_TOOLS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{req.tool} is a manual tool — perform it yourself and log it via "
                "/trajectory; it is not executed here."
            ),
        )
    spec = TOOLS.get(req.tool)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {req.tool}")
    kwargs, err = coerce_params(spec, req.params)
    if err:
        raise HTTPException(status_code=422, detail=err)
    try:
        with _bq_context(x_bigquery_access_token, x_bigquery_billing_project):
            result = spec["fn"](**kwargs)
    except HTTPException:
        raise  # missing-credential / auth errors propagate as real HTTP errors
    except Exception as exc:  # surface tool/query errors as a call outcome, like the UI
        return CallToolResponse(ok=False, error=f"{type(exc).__name__}: {exc}")
    return CallToolResponse(ok=True, result=result, fingerprint=trajectory.fingerprint(result))


@app.post("/trajectory", dependencies=[Depends(_require_secret)])
def save_trajectory(req: TrajectoryRequest) -> dict:
    location = trajectory.persist(
        req.task_id,
        req.contributor,
        req.session_token,
        [r.model_dump() for r in req.records],
    )
    return {"ok": True, "location": location, "records": len(req.records)}
