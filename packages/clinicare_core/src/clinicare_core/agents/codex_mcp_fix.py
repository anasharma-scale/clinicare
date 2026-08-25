"""Repo-local override of harbor's Codex agent: correct stdio MCP-server registration.

harbor's stock Codex adapter (`harbor.agents.installed.codex.Codex`) serializes a stdio
MCP server into Codex's `config.toml` by flattening command + args into a single
`command = "python -m mimic_tools.mcp_server"` line, with no `args` key. Codex treats
`command` as the executable name only (it does not shell-split it), so it tries to spawn a
binary literally named "python -m mimic_tools.mcp_server", the server never starts, and no
MCP tools surface — the agent then improvises via the shell. This subclass writes `command`
and `args` as separate keys, per Codex's config schema (matching the MCP spec / claude-code).

It also raises Codex's per-server MCP timeouts: the `mimic` server cold-starts DuckDB in a
background thread (serve-first), and under concurrency the initialize handshake can exceed
Codex's default window ("timed out handshaking with MCP server after 30s"), and the failure rate
climbs with concurrency. `startup_timeout_sec` covers the handshake; `tool_timeout_sec` covers
the slow first query. Both default to 120s, tunable via MCP_STARTUP_TIMEOUT_SEC.
Codex reads these ONLY from config.toml (no env var), which is why claude-code (MCP_TIMEOUT /
MCP_TOOL_TIMEOUT env, set in the task template) and gemini (settings.json, default 600s) are
handled differently — see the healthcare _template/task.toml note.

Use it via harbor's custom-agent flag. It ships in an installed package, so the import path
resolves from any working directory:

    uv run harbor run \
        --agent-import-path clinicare_core.agents.codex_mcp_fix:CodexMcpFixed -m openai/gpt-5.5 ...

Delete this once harbor fixes `_build_register_mcp_servers_command` upstream.
"""

from __future__ import annotations

import json
import os
import shlex
from typing import Any

from harbor.agents.installed.codex import Codex


class _WholeModelName(str):
    """A model id whose `.split("/")` is a no-op, so harbor's Codex.run() cannot collapse it.

    harbor's Codex.run() does `model = self.model_name.split("/")[-1]` before `codex --model`,
    which turns a PINNED proxy deployment id ("azure_ai/gpt-5.5") back into the load-balanced
    alias ("gpt-5.5") -- exactly what we need to avoid. `split("/", 1)` (used by harbor's
    pricing lookup) keeps its normal behaviour so cost accounting still resolves "gpt-5.5".
    """

    def split(self, sep: str | None = None, maxsplit: int = -1) -> list[str]:  # type: ignore[override]
        if sep == "/" and maxsplit == -1:
            return [str(self)]
        return str.split(self, sep, maxsplit)


class CodexMcpFixed(Codex):
    # Pin the Responses API to ONE proxy deployment (opt-in; empty = harbor's stock behaviour).
    #
    # WHY: codex speaks OpenAI's Responses API and replays the previous turn's encrypted
    # reasoning state on every subsequent turn. A load-balancing gateway can spread the
    # bare model groups ("gpt-5.5", "gpt-5.6-sol", "gpt-5.4") across deployments backed by
    # DIFFERENT upstream API keys, so turn 2 can land on a different org than turn 1 and the
    # blob fails to decrypt:
    #     BadRequestError ... code "invalid_encrypted_content"
    #     "This error occurs when load balancing Responses API across deployments with
    #      different API keys" ... Received Model Group=gpt-5.6-sol
    # It is fatal (`turn.failed` on the 2nd model request) and it still writes a score-0.0
    # reward.json, so it masquerades as a real result. The proxy-side fix is
    # `optional_pre_call_checks: [encrypted_content_affinity]`, which we cannot set; the
    # client-side equivalent is to address a single-deployment group instead of the alias.
    # Set CODEX_PIN_DEPLOYMENT=<prefix> to address a single-deployment group. Leave it unset
    # against a vendor endpoint or any gateway that does not load-balance the model group —
    # there is nothing to pin there.
    _PIN_ENV = "CODEX_PIN_DEPLOYMENT"

    def _pinned_model_name(self) -> str | None:
        """`<prefix>/<bare model>` when pinning is enabled, else None."""
        prefix = os.environ.get(self._PIN_ENV, "").strip().strip("/")
        if not prefix or not self.model_name:
            return None
        if self.model_name.count("/") > 1:
            # e.g. "openai/fireworks_ai/deepseek-v4-pro" -- the middle segment already names the
            # upstream provider, so there is no vendor alias to pin. Leave it alone.
            return None
        bare = self.model_name.split("/")[-1]
        pinned = f"{prefix}/{bare}"
        return None if pinned == self.model_name else pinned

    async def run(self, instruction: str, *args: Any, **kwargs: Any) -> None:
        # No @with_prompt_template here on purpose: the parent's run() is already decorated, so
        # rendering happens exactly once inside super().run().
        pinned = self._pinned_model_name()
        if pinned is None:
            return await super().run(instruction, *args, **kwargs)
        original = self.model_name
        # _WholeModelName keeps the deployment prefix on the wire; restored immediately after
        # so trajectory/pricing bookkeeping sees the plain alias it expects.
        self.model_name = _WholeModelName(pinned)
        self.logger.info("Codex model pinned for the wire: %s -> %s", original, pinned)
        try:
            return await super().run(instruction, *args, **kwargs)
        finally:
            self.model_name = original

    # Force the Responses API onto HTTP instead of its WebSocket transport (opt-in).
    #
    # WHY: some gateway edges return a bodiless 403 to the websocket UPGRADE on
    # `/v1/responses` while plain HTTP to the same route
    # returns 200. codex retries 5x then exits 1, killing the trial before its first tool call.
    #
    # HOW: `supports_websockets` is a `ModelProviderInfo` field, so the switch is a custom provider
    # with it false, selected via top-level `model_provider` (openai/codex#13041, #13103).
    #
    # Two things that DON'T work, so nobody retries them: `--ak features.…=false` (harbor silently
    # drops keys that aren't declared CLI_FLAGS descriptors), and a `[features]` table in
    # config.toml (written and ignored -- it is a feature name, not the transport switch).
    _HTTP_ONLY_ENV = "CODEX_HTTP_ONLY"
    _HTTP_PROVIDER = "openai_http"

    def _build_http_only_command(self) -> str | None:
        """Define a websocket-free model provider and select it, when opted in."""
        if os.environ.get(self._HTTP_ONLY_ENV) != "1":
            return None
        base_url = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
        if not base_url:
            # Fail loudly rather than emitting a provider with no base_url, which would send codex
            # to api.openai.com and fail with a confusing 401 instead of naming the real problem.
            raise ValueError(
                f"{self._HTTP_ONLY_ENV}=1 requires OPENAI_BASE_URL so the HTTP-only provider can "
                "point at the proxy; codex only reads the base url from config.toml."
            )
        lines = [
            f'model_provider = "{self._HTTP_PROVIDER}"',
            "",
            f"[model_providers.{self._HTTP_PROVIDER}]",
            'name = "OpenAI-compatible, HTTP only"',
            f'base_url = "{base_url}"',
            'env_key = "OPENAI_API_KEY"',
            'wire_api = "responses"',
            "supports_websockets = false",
        ]
        return f'echo {shlex.quote(chr(10).join(lines))} >> "$CODEX_HOME/config.toml"'

    def _build_register_mcp_servers_command(self) -> str | None:
        if not self.mcp_servers:
            # Still emit the features block: it is independent of MCP registration, and returning
            # None here on a no-MCP system would silently drop the transport override.
            return self._build_http_only_command()
        timeout_sec = int(os.environ.get("MCP_STARTUP_TIMEOUT_SEC", "120"))
        parts: list[str] = []
        if (http_only := self._build_http_only_command()) is not None:
            parts.append(http_only)
        for server in self.mcp_servers:
            lines = [f"[mcp_servers.{server.name}]"]
            if server.transport == "stdio":
                lines.append(f"command = {json.dumps(server.command)}")
                if server.args:
                    lines.append(f"args = {json.dumps(list(server.args))}")
            else:
                lines.append(f"url = {json.dumps(server.url)}")
            lines.append(f"startup_timeout_sec = {timeout_sec}")
            lines.append(f"tool_timeout_sec = {timeout_sec}")
            parts.append(f'echo {shlex.quote(chr(10).join(lines))} >> "$CODEX_HOME/config.toml"')
            # No `[mcp_servers.<name>.env]` table needed: Codex scrubs the spawned server's env, but
            # the proxy shim repopulates the vars it needs (MIMIC_TOOLS_URL / _API_KEY) from the
            # launching process's /proc environ at startup — see mimic_tools.mcp_server
            # ._recover_proxy_env. Proxy-only, so the shim holds no data credentials at all.
        return " && ".join(parts)
