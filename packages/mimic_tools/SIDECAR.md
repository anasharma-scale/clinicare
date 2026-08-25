# mimic-tools sidecar — credential-isolated data access

## Why

The agent reaches MIMIC through the `mimic` tools. But if the tool server runs *inside* the
agent's container, it needs the data credentials there — and a code-capable agent can read them
(`env | grep`, credential files, the instance metadata endpoint) and query the raw tables
directly, bypassing the governed tool surface entirely. Agents with shell access do try this.

Full-database access **through the tools** is fine and intended — the scoping is at the task
level, not the database level. The problem is only the *ungoverned* path. The sidecar removes it
without restricting what the tools can do.

This matters for anyone publishing a CliniCARE result: if a submission can bypass the tools, its
numbers aren't comparable to one that can't, and you cannot tell from the output which happened.

## Design

Split the credential and egress boundary out of the agent's container:

```
┌─ agent container ───────────┐        ┌─ mimic-tools sidecar ───────────┐
│ mcp_server.py (PROXY mode)  │  HTTP  │ python -m mimic_tools.serve     │
│  • no data credentials      │──────▶ │  • the ONLY MIMIC access        │
│  • egress: ONLY the sidecar │ x-api- │  • read-only Parquet bind mount │
│    and the model endpoint   │  key   │  • full run_sql over all tables │
└─────────────────────────────┘        └─────────────────────────────────┘
```

The tool **surface is identical** to running the tools in-process — same names, params, schemas,
outputs — so the agent can't tell the difference and trajectories stay comparable. `run_sql` over
all 41 tables still works; it just executes in the sidecar. The only thing the agent loses is the
ability to reach the data store itself.

## Proxy-only

`mcp_server.py` runs in **proxy mode only** — there is no in-container path to the data:

| process | role |
|---|---|
| agent's shim (`python -m mimic_tools.mcp_server`) | holds no credentials, runs no database; forwards every call to `${MIMIC_TOOLS_URL}/call-tool` with `x-api-key`. Fails loudly at startup if `MIMIC_TOOLS_URL` is unset. |
| sidecar (`python -m mimic_tools.serve`) | preflights the data and **exits non-zero if it can't read it**, then serves the canonical surface via `api.py`. |

The shim no longer imports `db`, so the agent container has no code path to the data at all.

The sidecar's fail-fast preflight is deliberate. Without it a misconfigured data root yields a
sidecar that comes up "healthy" and then returns empty for every tool call, which agents report
as "Indeterminate – lack of data" — a plausible wrong answer instead of an error.

## How it's wired

`build_tasks.py` sets this up; you don't hand-edit anything.

1. **Image** — one image runs both roles (agent = `mcp_server`, sidecar = `serve`), differing
   only by command and environment. Build with `bash scripts/build_image.sh`.
2. **Sidecar** — `build_tasks.py` writes a single `<out_dir>/_sidecar.compose.yml`, merged in at
   run time with `harbor run --extra-docker-compose <out_dir>/_sidecar.compose.yml`. It runs the
   sidecar, bind-mounts your Parquet tree **read-only**, mounts the policy corpus, and injects
   the sidecar's coordinates into the agent container.

   *Why one shared compose rather than a per-task `environment/docker-compose.yaml`:* the latter
   forces some Harbor backends into compose mode (DinD + host networking), which **disables
   `network_mode=allowlist`** — silently removing the egress lockdown this whole design rests on.

3. **Egress lockdown** — the agent's `task.toml` sets `network_mode = "allowlist"`, so Harbor
   routes all its outbound TCP through an egress-control sidecar (nftables + a GOST allowlist).
   That blocks the open web and the instance-metadata endpoint, permitting only the model endpoint
   and `mimic-tools.internal:8799`. This is the load-bearing step; without it the split is
   cosmetic.

   Every allowlist entry **must be a dotted hostname** — some backends validate the list
   server-side and reject a bare label, which kills every trial before the agent starts. That is
   why the sidecar is dialed via the `mimic-tools.internal` network alias rather than its bare
   compose service name. Keep the alias, the allowlist entry, and the `MIMIC_TOOLS_URL` default in
   lockstep; they are one fact spelled in three places.

## Why a leaked api-key is harmless

The `x-api-key` lives in the agent container — the shim sends it — so treat it as readable by the
agent. That's fine: it grants **tool-level** access, exactly what the agent is allowed. It does
not grant a route to the data store; that never leaves the sidecar. You are protecting the
credentials and the data egress, not the tool API.

It is still required, and the sidecar still refuses to start without it. The auth check is
`if secret and x_api_key != secret`, so an *unset* secret disables auth entirely — and the sidecar
binds `0.0.0.0:8799`. On a cloud VM with a permissive security group that quietly becomes an
unauthenticated MIMIC endpoint on the public internet.

## Policy tools

`list_policy_docs` / `search_policy` / `read_policy` read the corpus, which is staged into the
**sidecar** (the compose mounts it) with `MIMIC_POLICY_TOOLS=1`. The agent sets the same flag only
so its tool *list* matches; it holds no corpus.

## Self-hosting the sidecar

Two defaults are deliberately conservative, because the failure mode of getting them wrong is an
open, credentialed MIMIC endpoint that looks healthy:

| default | effect | when to change it |
|---|---|---|
| `MIMIC_API_SECRET` required | `serve` refuses to start without a shared secret | never on a reachable instance; `MIMIC_REQUIRE_API_SECRET=0` only for a genuinely isolated local one |
| `MIMIC_TOOLS_HOST=127.0.0.1` | binds loopback only | set `0.0.0.0` when the agent runs in another container or host — the trial compose file already does |

`run_sql` is confined at the DuckDB connection, not by inspecting SQL text: the connection is
opened, the MIMIC views are created, and then file access is restricted to `MIMIC_DATA_ROOT` and
the configuration is locked. This is what stops a `SELECT ... FROM read_text('/proc/self/environ')`
from handing the agent the sidecar's own credentials — the bypass this whole design exists to
remove. It needs `duckdb>=1.2`; on anything older the sidecar refuses to serve rather than serve
unconfined.

## BigQuery

The shim works unchanged against a BigQuery-backed sidecar — set `MIMIC_BACKEND=bigquery` on the
sidecar and give it egress to `bigquery.googleapis.com` plus an ADC credential. Leave
`MIMIC_BQ_PER_REQUEST_AUTH` off unless you are running a genuinely multi-tenant service: a
forwarded access token carries no refresh material and dies about an hour into a sweep.

## Verifying it locally

```bash
# 1. the sidecar, credentialed
MIMIC_BACKEND=duckdb MIMIC_DATA_ROOT=/path/to/mimic-parquet \
  MIMIC_API_SECRET=dev python -m mimic_tools.serve

# 2. the shim in proxy mode against it — holding no data configuration at all
MIMIC_TOOLS_URL=http://127.0.0.1:8799 MIMIC_TOOLS_API_KEY=dev \
  python -m mimic_tools.mcp_server --selftest
```

The check that matters is the second command working *without* `MIMIC_DATA_ROOT` set — that is
the isolation being real rather than incidental.
