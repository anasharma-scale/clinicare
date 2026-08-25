"""MCP (stdio) server exposing the canonical MIMIC tool surface (tools.py) to an agent.

This is the third consumer of the SAME canonical surface, alongside the Streamlit
console (app.py) and the hosted FastAPI backend (api.py). It reads the declarative
registry (tool_registry.TOOLS) and presents every executable data tool as an MCP tool,
with its JSON-Schema generated from the registry's param specs — so the agent sees the
identical surface (names, params, docs) a contributor used to build the gold trajectory.

Transport: stdio. Harbor wires this into an agent via the task's
`[[environment.mcp_servers]]` (transport = "stdio", command = "python",
args = ["-m", "mimic_tools.mcp_server"]). The server process inherits the trial
container's environment, which supplies MIMIC_TOOLS_URL + MIMIC_TOOLS_API_KEY.

This server runs in **proxy mode only**: it holds NO credentials and runs no data backend.
It forwards every tool call to a `mimic-tools` sidecar's `POST /call-tool` (api.py, run by
`mimic_tools.serve`) over HTTP at MIMIC_TOOLS_URL, authenticating with `x-api-key`
(MIMIC_TOOLS_API_KEY). The sidecar is the only process with credentials + data egress, so an
agent with a shell cannot read creds or reach the data store directly — it can only go through
the governed tools. See SIDECAR.md. If the agent env supplies a BigQuery identity
(MIMIC_BQ_ACCESS_TOKEN / MIMIC_BQ_BILLING_PROJECT) it is passed through, so the same shim works
against a BigQuery-backed sidecar for a public release.

Run locally to sanity-check the surface (lists tools, exits):
    uv run python -m mimic_tools.mcp_server --selftest
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .tool_registry import TOOLS, apply_policy_gate

SERVER_NAME = "mimic-iv"


# ------------------------------- proxy mode -------------------------------- #


def _proxy_url() -> str | None:
    """The mimic-tools sidecar base URL, or None when this process runs tools directly."""
    url = os.environ.get("MIMIC_TOOLS_URL", "").strip().rstrip("/")
    return url or None


# Vars the proxy shim needs from its environment. Agent CLIs differ in whether they forward the
# container env to a spawned stdio MCP server: claude-code does; codex and gemini-cli SCRUB it
# (and Harbor's MCP config has no per-server `env` field to declare them). Scrubbed, the shim can't
# reach/authenticate the sidecar: MIMIC_TOOLS_URL is empty so main() exits 3 (codex → "no tools"),
# or MIMIC_TOOLS_API_KEY is empty so every call 401s (gemini). _recover_proxy_env repopulates any
# missing var from outside the scrubbed env, making the shim agent-agnostic (no per-agent config).
_PROXY_ENV_VARS = (
    "MIMIC_TOOLS_URL",
    "MIMIC_TOOLS_API_KEY",
    "MIMIC_TOOLS_TIMEOUT",
    "MIMIC_BQ_ACCESS_TOKEN",
    "MIMIC_BQ_BILLING_PROJECT",
    # Recovered so the policy-OFF ablation stays faithful under codex: the tool gate fails OPEN
    # (tool_registry._policy_tools_enabled), so an explicit "0" that got scrubbed would silently
    # re-enable the policy tools and the ablation would measure nothing.
    "MIMIC_POLICY_TOOLS",
)


def _parse_env_file(path: str) -> dict[str, str]:
    """Parse a KEY=VALUE env file (blank / `#` lines ignored). Missing/unreadable → {}."""
    out: dict[str, str] = {}
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def _read_proc_environ(pid: int) -> dict[str, str]:
    """Read /proc/<pid>/environ (NUL-separated KEY=VALUE). Readable when <pid> shares our UID —
    the agent CLI that spawned us does. Missing/unreadable/non-Linux → {}."""
    out: dict[str, str] = {}
    try:
        raw = open(f"/proc/{pid}/environ", "rb").read()
    except OSError:
        return out
    for kv in raw.split(b"\0"):
        if b"=" in kv:
            k, _, v = kv.partition(b"=")
            try:
                out[k.decode()] = v.decode()
            except UnicodeDecodeError:
                pass
    return out


def _recover_proxy_env() -> None:
    """Repopulate proxy vars scrubbed by the launching agent CLI (codex / gemini-cli).

    Values already in os.environ win (claude-code forwards the env, so it is untouched). Missing
    vars are recovered from, in order: an explicit KEY=VALUE file at $MIMIC_TOOLS_ENV_FILE (default
    /etc/mimic-tools/proxy.env, if present); then the environ of the launching agent process
    (os.getppid()) and of PID 1 — both hold the full injected container env. Delete once Harbor's
    MCP config grows a per-server `env` field and each installed adapter forwards it."""
    missing = [v for v in _PROXY_ENV_VARS if not os.environ.get(v)]
    if not missing:
        return
    sources = [
        _parse_env_file(os.environ.get("MIMIC_TOOLS_ENV_FILE", "/etc/mimic-tools/proxy.env"))
    ]
    for pid in (os.getppid(), 1):
        sources.append(_read_proc_environ(pid))
    for var in missing:
        for src in sources:
            if src.get(var):
                os.environ[var] = src[var]
                break
    # Say so when a var could not be recovered from any source. A silently reduced tool surface is
    # what made the policy-tools outage look like an intentional ablation for a whole sweep, so the
    # shim now announces it on stderr (which the agent CLI captures into its own log).
    unrecovered = [v for v in missing if not os.environ.get(v)]
    if unrecovered:
        print(
            f"[mimic-shim] WARNING: could not recover {', '.join(unrecovered)} from the env file, "
            f"the parent process, or PID 1 — the served tool surface may be incomplete.",
            file=sys.stderr,
            flush=True,
        )


#: Key under which a non-object tool result is nested by `_as_record`.
RESULT_ITEMS_KEY = "items"


def _as_record(result: Any) -> Any:
    """Return `result` as a JSON object, nesting any non-object payload under `items`.

    Works around a gemini-cli bug, not a spec violation here. We send the result as JSON text and
    never set `structuredContent`; gemini-cli's `fixStructuredContent` parses our text into that
    field without checking it is an object, then its own SDK validates it as
    `record(string, unknown)` and throws `Invalid input: expected record, received <type>`. The
    model sees a broken tool and stops using it. It hits every list-returning tool, so clinical
    retrieval degrades, not just policy grounding; object-returning tools and the other harnesses
    are unaffected.

    Declaring `outputSchema` instead would break us (the python SDK then demands a structured
    return); emitting real `structuredContent` needs this same wrapper anyway.

    INVARIANT -- shim only. Do not move this into the sidecar (`api.py`): `/call-tool` must keep
    returning bare arrays, because `tests/judge.py::_materialize_policy_corpus` requires
    `isinstance(docs, list)` (else policy grounding silently stops scoring) and
    `trajectory.fingerprint()` reads the raw return for its row and column counts.
    """
    if isinstance(result, dict):
        return result
    return {RESULT_ITEMS_KEY: result}


def _run_tool_remote(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Forward one tool call to the sidecar's POST /call-tool and mirror the direct path's
    output contract: the tool result as a JSON string on success, `ERROR: <msg>` on failure."""
    url = f"{_proxy_url()}/call-tool"
    body = json.dumps({"tool": name, "params": arguments or {}}).encode()
    headers = {"Content-Type": "application/json"}
    if key := os.environ.get("MIMIC_TOOLS_API_KEY"):
        headers["x-api-key"] = key
    # Pass a per-request BigQuery identity through when present (public / BigQuery sidecar).
    for env_var, header in (
        ("MIMIC_BQ_ACCESS_TOKEN", "X-BigQuery-Access-Token"),
        ("MIMIC_BQ_BILLING_PROJECT", "X-BigQuery-Billing-Project"),
    ):
        if v := os.environ.get(env_var):
            headers[header] = v
    timeout = float(os.environ.get("MIMIC_TOOLS_TIMEOUT", "600"))
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    # Connection-level failures get a bounded retry: the agent can issue its first tool call
    # before the sidecar's healthcheck passes (no depends_on links main→sidecar). HTTP errors
    # (4xx/5xx) are real tool outcomes and are NOT retried. time.sleep is fine — tool calls run
    # off the event loop (anyio.to_thread), so this blocks only the worker thread.
    last_exc = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except Exception:  # noqa: BLE001 — non-JSON body; use it raw
                pass
            return [types.TextContent(type="text", text=f"ERROR: {exc.code}: {detail}")]
        except Exception as exc:  # noqa: BLE001 — connection/timeout: retry, then surface
            last_exc = exc
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
    else:
        return [
            types.TextContent(
                type="text",
                text=f"ERROR: could not reach mimic-tools service after retries: "
                f"{type(last_exc).__name__}: {last_exc}",
            )
        ]
    if not payload.get("ok"):
        return [
            types.TextContent(
                type="text", text=f"ERROR: {payload.get('error') or 'tool call failed'}"
            )
        ]
    result = _as_record(payload.get("result"))
    return [types.TextContent(type="text", text=json.dumps(result, default=str))]


# --------------------------- schema generation ----------------------------- #

_JSON_TYPE = {"int": "integer", "str": "string", "text": "string"}


def _input_schema(spec: dict) -> dict:
    """JSON Schema for a tool's params, derived from the registry param specs."""
    props: dict[str, Any] = {}
    required: list[str] = []
    for p in spec["params"]:
        name, kind = p["name"], p["kind"]
        prop: dict[str, Any] = {"type": _JSON_TYPE.get(kind, "string")}
        desc = p.get("help") or p.get("placeholder")
        if kind == "enum":
            opts = [o for o in p.get("options", []) if o != ""]
            if opts:
                prop["enum"] = opts
        elif kind == "enum_dynamic":
            src = p.get("source")
            hint = f"Free-text value from {src[1]}.{src[0]}." if src else ""
            desc = f"{desc + ' ' if desc else ''}{hint}".strip() or None
        if p.get("multi"):
            # Widen to "one value OR a list of them". anyOf (not a bare array) keeps every
            # existing single-value caller — the contributor UI, prior traces — valid.
            prop = {"anyOf": [prop, {"type": "array", "items": dict(prop)}]}
        if "default" in p:
            prop["default"] = p["default"]
        if desc:
            prop["description"] = desc
        props[name] = prop
        if p.get("required"):
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def _description(name: str, spec: dict) -> str:
    parts = [spec.get("doc", name)]
    tables = spec.get("tables") or []
    if tables:
        parts.append(f"Reads: {', '.join(tables)}.")
    return " ".join(parts)


def build_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=name,
            description=_description(name, spec),
            inputSchema=_input_schema(spec),
        )
        for name, spec in TOOLS.items()
    ]


# --------------------------------- server ---------------------------------- #


def _run_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    # Proxy-only: every call forwards to the credentialed sidecar, which owns all data access. A
    # missing MIMIC_TOOLS_URL is a misconfiguration, caught loudly at startup in main().
    return _run_tool_remote(name, arguments)


def build_server() -> Server:
    server = Server(SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:  # noqa: D401
        return build_tools()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        # tools.py is synchronous and IO-bound (DuckDB / BigQuery); run off the event loop.
        return await anyio.to_thread.run_sync(_run_tool, name, arguments)

    return server


async def _serve() -> None:
    # Proxy-only: this process runs no local data backend, so there is nothing to warm — the
    # sidecar preflights its own data access at startup. Open the stdio transport
    # and serve; the first tool call forwards to the sidecar (which is health-gated before the
    # agent starts on docker via `docker compose up --wait`, and independently deployed on modal).
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def _apply_recovered_policy_tools() -> None:
    """Re-evaluate the policy-tool gate AFTER env recovery, in both directions.

    `tool_registry` decides `TOOLS.update(POLICY_TOOLS)` at IMPORT time, which runs before main()
    calls `_recover_proxy_env()`. The gate fails OPEN (an unset var means policy-ON, the normal
    condition), so a scrubbed var cannot hide the policy tools from an agent that should have them.

    But fail-open plus import-order leaves the mirror-image hole on the `--no-policy` ablation: that
    build sets MIMIC_POLICY_TOOLS=0, codex scrubs it, the import-time gate sees an empty var and
    registers the tools anyway. Recovering the "0" afterwards does not undo that on its own, so a
    policy-OFF trial would silently run WITH policy tools and the ablation would measure nothing.
    Re-applying the gate here closes both directions: add the tools when they are enabled but missing,
    remove them when they were explicitly disabled. Either transition is logged so the condition is
    visible in the trial's stderr rather than inferred.
    """
    from .tool_registry import POLICY_TOOLS, TOOLS, _policy_tools_enabled

    enabled = _policy_tools_enabled()
    present = set(POLICY_TOOLS) <= set(TOOLS)
    if enabled and not present:
        TOOLS.update(POLICY_TOOLS)
        print(
            f"[mimic-mcp] policy tools registered after env recovery: {', '.join(POLICY_TOOLS)}",
            file=sys.stderr,
            flush=True,
        )
    elif not enabled and any(name in TOOLS for name in POLICY_TOOLS):
        for name in POLICY_TOOLS:
            TOOLS.pop(name, None)
        print(
            "[mimic-mcp] policy tools REMOVED after env recovery: MIMIC_POLICY_TOOLS is explicitly "
            f"off ({os.environ.get('MIMIC_POLICY_TOOLS')!r}); this is a policy-OFF trial",
            file=sys.stderr,
            flush=True,
        )


def main() -> None:
    # Recover + re-gate BEFORE anything reads the tool list (including --selftest): the gate was
    # evaluated at tool_registry import time, which happens before this function runs and therefore
    # before the scrubbed env has been repaired.
    _recover_proxy_env()
    apply_policy_gate()
    if "--selftest" in sys.argv:
        tools = build_tools()
        print(f"{SERVER_NAME}: {len(tools)} tools")
        for t in tools:
            req = t.inputSchema.get("required", [])
            print(f"  - {t.name}({', '.join(req)})")
        return
    _recover_proxy_env()  # recover MIMIC_TOOLS_URL/_API_KEY if the launching agent CLI scrubbed them
    _apply_recovered_policy_tools()
    if _proxy_url() is None:
        # Proxy mode is the only mode. Without a sidecar URL this server has no way to reach the
        # data — fail loudly at startup so the trial errors immediately instead of every tool
        # call returning a connection error.
        print(
            "[mimic-mcp] FATAL: MIMIC_TOOLS_URL is not set. This server runs in proxy mode only; it "
            "must point at a mimic-tools sidecar (docker: http://mimic-tools.internal:8799, the "
            "compose network alias). See SIDECAR.md.",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(3)
    anyio.run(_serve)


if __name__ == "__main__":
    main()
