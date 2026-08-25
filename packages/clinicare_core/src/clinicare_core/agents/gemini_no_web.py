"""Gemini-CLI with the built-in web tools disabled (frozen-corpus evaluation).

CliniCare grounds external claims in a staged policy corpus, not the open web, so the agent's
built-in web search must be off. The stock harbor ``GeminiCli`` adapter rewrites
``~/.gemini/settings.json`` on every run (``_build_settings_config``) with no tool denylist, and
exposes no CLI flag for one — so we subclass it and inject gemini-cli's ``excludeTools`` denylist
into that run-time config.

NB: overriding ``install()`` does NOT work — the parent's run-time write (``> settings.json``)
clobbers any install-time file, so the override has to be on the config builder itself.

Mirrors ``codex_mcp_fix.py``; delete once harbor exposes a settings/excludeTools hook upstream.

Run:  --agent-import-path clinicare_core.agents.gemini_no_web:GeminiNoWeb
"""

from __future__ import annotations

from typing import Any, override

from harbor.agents.installed.gemini_cli import GeminiCli

# gemini-cli built-in web tools to strip. google_web_search is the one seen in our runs;
# web_fetch is gemini-cli's other web tool, excluded for completeness.
_WEB_TOOLS = ["google_web_search", "web_fetch"]


class GeminiNoWeb(GeminiCli):
    """GeminiCli with the built-in web tools removed via the settings ``excludeTools`` denylist."""

    @override
    def _build_settings_config(
        self, model: str | None = None, auth_type: str | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        config, model_alias = super()._build_settings_config(model, auth_type)
        # force a settings write even when the parent produced none, so the denylist always lands
        config = config or {}
        config["excludeTools"] = list(_WEB_TOOLS)
        return config, model_alias
