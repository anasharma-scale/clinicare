"""MIMIC-IV canonical tool kernel.

The shared, dependency-clean tool surface. Every consumer imports the same module, so the tools
an agent calls are the tools a human explores with:
  - the agent, via the stdio MCP server (mcp_server.py) proxying to the sidecar (api.py / serve.py)
  - the Streamlit console (streamlit_app.py)

Import the surface from here:
    from mimic_tools.tool_registry import TOOLS, coerce_params
    from mimic_tools import tools, db

Keep this package free of UI/web/agent dependencies — no streamlit, fastapi or agent-framework
imports in tools.py / db.py / tool_registry.py — so every consumer stays cheap to build on it.
"""
