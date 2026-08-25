"""Pull-based MIMIC tool console for benchmark contributors.

Design goal: nothing is fetched unless the contributor *explicitly* invokes a
tool — exactly the surface the agent sees. The ordered list of calls a
contributor makes to solve a task IS the gold trajectory, so we log every call
(tool, params, result fingerprint, whether it was load-bearing) to JSONL.

There is deliberately NO auto-load / chart-browser behavior: "load patient X"
does not fan out to every tool. We want to know which tools were actually used.

Run:
    uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import datetime
import uuid

import pandas as pd
import streamlit as st
from mimic_tools import db, tools, trajectory
from mimic_tools.tool_registry import TOOLS, coerce_params

# The agent harness imports mimic_tools.* directly and never runs this file, so its behavior

st.set_page_config(page_title="MIMIC Tool Console", layout="wide")

CTX_IDS = ["subject_id", "hadm_id", "stay_id", "note_id"]


# --------------------- Tool registry ------------------------------------- #
# The canonical declarative tool surface lives in tool_registry.py so this Streamlit
# console and the FastAPI backend (api.py) render the identical surface from ONE source
# — same principle that keeps tools.py canonical between the console and the agent harness.


# --------------------- Helpers ------------------------------------------- #


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _persist() -> None:
    """Rewrite the whole trajectory file via the shared writer, so this console and the FastAPI
    backend emit identical records instead of two hand-synced copies."""
    trajectory.persist(
        st.session_state.task_id,
        st.session_state.contributor,
        st.session_state.session_token,
        st.session_state.transcript,
    )


def _distinct_options(column: str, table: str) -> list[str]:
    """Distinct values of a controlled-vocabulary column, for dropdown population.
    Cached; column/table come from the registry (not user input)."""
    try:
        res = tools.run_sql(
            f"SELECT DISTINCT {column} AS v FROM {table} WHERE {column} IS NOT NULL ORDER BY v",
            max_rows=500,
        )
        return [""] + [r["v"] for r in res["rows"]]
    except Exception:
        return [""]


def _pin_buttons(seq: int, rows: list[dict]) -> None:
    """Surface id values from a table result as buttons that prefill the next call."""
    present = [c for c in CTX_IDS if rows and c in rows[0]]
    if not present:
        return
    st.caption("Pin an id to prefill the next call:")
    for col in present:
        vals: list = []
        for r in rows:
            v = r.get(col)
            if v is not None and v not in vals:
                vals.append(v)
            if len(vals) >= 8:
                break
        if not vals:
            continue
        bcols = st.columns(min(len(vals), 4))
        for i, v in enumerate(vals):
            if bcols[i % len(bcols)].button(f"{col}={v}", key=f"pin_{seq}_{col}_{v}"):
                st.session_state.ctx[col] = v
                st.rerun()


def _kv_table(d: dict) -> pd.DataFrame:
    # Stringify values: a single "value" column holds mixed types (str/int/None), which
    # Arrow can't serialize — it would infer int64 then choke on the first string.
    return pd.DataFrame([{"field": k, "value": "" if v is None else str(v)} for k, v in d.items()])


def _render_card(d: dict) -> None:
    """Render a card dict readably: scalar fields as one field/value table, nested
    dict fields as their own small table, list fields as titled sub-tables — not raw JSON."""
    scalars = {k: v for k, v in d.items() if not isinstance(v, (list, dict))}
    if scalars:
        st.dataframe(_kv_table(scalars), width="stretch", hide_index=True)
    for key, val in d.items():
        if isinstance(val, dict):
            st.markdown(f"**{key}**")
            st.dataframe(_kv_table(val), width="stretch", hide_index=True)
        elif isinstance(val, list):
            if val:
                st.markdown(f"**{key}** ({len(val)})")
                st.dataframe(pd.DataFrame(val), width="stretch", hide_index=True)
            else:
                st.caption(f"{key}: none")


def _render_result(rec: dict) -> None:
    result = rec["result"]
    if result is None:
        st.write("`None` — no match.")
        return
    if isinstance(result, list):
        if not result:
            st.write("Empty result (0 rows).")
            return
        st.caption(f"{len(result)} row(s)")
        st.dataframe(pd.DataFrame(result), width="stretch", hide_index=True)
        _pin_buttons(rec["seq"], result)
        return
    if isinstance(result, dict):
        if "rows" in result and "columns" in result:  # run_sql
            st.caption(
                f"returned {result['returned']} row(s)"
                + (" · truncated" if result.get("truncated") else "")
            )
            if result.get("note"):
                st.warning(result["note"])
            if result["rows"]:
                st.dataframe(pd.DataFrame(result["rows"]), width="stretch", hide_index=True)
            _pin_buttons(rec["seq"], result["rows"])
            return
        if "text" in result:  # get_note
            st.json({k: v for k, v in result.items() if k != "text"})
            st.text(result["text"])
            return
        _render_card(result)  # cards / nested (e.g. get_admission_details)
        return
    st.write(result)


# --------------------- Session state init -------------------------------- #


st.session_state.setdefault("transcript", [])
st.session_state.setdefault("ctx", {})
st.session_state.setdefault("session_token", uuid.uuid4().hex[:8])
st.session_state.setdefault("contributor", "")
st.session_state.setdefault("task_id", "")


# --------------------- Sidebar: session identity ------------------------- #


with st.sidebar:
    st.header("Session")
    st.session_state.contributor = st.text_input("Contributor", value=st.session_state.contributor)
    st.session_state.task_id = st.text_input(
        "Task ID",
        value=st.session_state.task_id,
        help="Which benchmark task you're solving — keys the trajectory log.",
    )
    st.caption(
        f"Session `{st.session_state.session_token}` · {len(st.session_state.transcript)} call(s)"
    )
    if st.session_state.transcript:
        st.caption(
            "Logging → `"
            + trajectory.filename(
                st.session_state.task_id,
                st.session_state.contributor,
                st.session_state.session_token,
            )
            + "`"
        )
    if st.button("New session (clear transcript)"):
        st.session_state.transcript = []
        st.session_state.ctx = {}
        st.session_state.session_token = uuid.uuid4().hex[:8]
        st.rerun()
    st.divider()
    st.caption("Data: MIMIC-IV v3.1 + Note v2.2 + ED v2.2 · local Parquet via DuckDB")
    st.caption("Pull model: data appears only when you call a tool.")


st.title("MIMIC Tool Console")
st.caption("Invoke tools the way the agent would. Your call sequence is the gold trajectory.")


# --------------------- Schema reference (for run_sql) -------------------- #


def _schema_text(sch: dict) -> str:
    """Full schema as a plain-text doc to paste into an LLM for run_sql help."""
    lines = [
        "MIMIC tool-surface schema — reference for writing run_sql queries.",
        f"Backend: {db.BACKEND}. Read-only, single SELECT / WITH statement only.",
        "Use these logical table names (identical on every backend).",
        "Compare timestamp columns to literals via CAST(... AS TIMESTAMP).",
        "Queries are patient-scoped in practice; labevents/chartevents are very large.",
        "",
    ]
    by_module: dict[str, list[str]] = {}
    for logical, (module, _t) in db.TABLES.items():
        if logical in sch:
            by_module.setdefault(module, []).append(logical)
    for module, tbls in by_module.items():
        lines.append(f"# {module}")
        lines.extend(f"{t}({', '.join(c['name'] for c in sch[t])})" for t in tbls)
        lines.append("")
    return "\n".join(lines)


with st.expander("📖 Table schema — reference for run_sql", expanded=False):
    try:
        with st.spinner("Loading table schema from the backend…"):
            _sch = db.schema()
    except Exception as exc:  # surface a backend/credential failure instead of spinning
        _sch = {}
        st.error(
            f"Couldn't load the MIMIC **{db.BACKEND}** backend: {exc}\n\n"
            "On DuckDB, check MIMIC_DATA_ROOT points at a complete Parquet tree (see "
            "DATA_ACCESS.md); on BigQuery, check your credentials. Then reload the page."
        )
    if _sch:
        st.caption(
            f"{len(_sch)} tables on the **{db.BACKEND}** backend — same logical names on every "
            "backend. Use these in run_sql; compare timestamps via `CAST(... AS TIMESTAMP)`."
        )
        st.download_button(
            "⬇ Download full schema (paste into an LLM for SQL help)",
            data=_schema_text(_sch),
            file_name=f"mimic_schema_{db.BACKEND}.txt",
            mime="text/plain",
        )
        _t = st.selectbox("Table", sorted(_sch), key="schema_table")
        if _t:
            # _sch[_t] is now a list of {name, type, description} dicts → one row per column.
            st.dataframe(pd.DataFrame(_sch[_t]), width="stretch", hide_index=True)


# --------------------- Call a tool --------------------------------------- #


st.subheader("Call a tool")

tool_name = st.selectbox("Tool", list(TOOLS.keys()), key="tool_select")
spec = TOOLS[tool_name]
st.caption(spec["doc"])

with st.form("call_form", clear_on_submit=False):
    raw_inputs: dict = {}
    cols = st.columns(2)
    for i, p in enumerate(spec["params"]):
        name = p["name"]
        label = name + (" *" if p.get("required") else "")
        help_ = p.get("help")
        # Prefill id-like params from shared context so chaining is cheap.
        prefill = (
            str(st.session_state.ctx.get(name, ""))
            if name in CTX_IDS
            else str(p.get("default", ""))
        )
        if p["kind"] == "text":
            raw_inputs[name] = st.text_area(label, value="", height=130, help=help_)
        elif p["kind"] == "enum":
            raw_inputs[name] = cols[i % 2].selectbox(label, options=p["options"], help=help_)
        elif p["kind"] == "enum_dynamic":
            raw_inputs[name] = cols[i % 2].selectbox(
                label, options=_distinct_options(*p["source"]), help=help_
            )
        else:  # int | str
            raw_inputs[name] = cols[i % 2].text_input(label, value=prefill, help=help_)
    submitted = st.form_submit_button("Call", type="primary")

if submitted:
    kwargs, err = coerce_params(spec, raw_inputs)
    if err:
        st.error(err)
    else:
        try:
            with st.spinner(f"{tool_name}(...)"):
                result = spec["fn"](**kwargs)
            ok, error = True, None
        except Exception as exc:  # surface tool/query errors as a call outcome
            result, ok, error = None, False, f"{type(exc).__name__}: {exc}"
        st.session_state.transcript.append(
            {
                "seq": len(st.session_state.transcript) + 1,
                "ts": _now(),
                "tool": tool_name,
                "params": kwargs,
                "ok": ok,
                "error": error,
                "result": result,
                "load_bearing": False,
            }
        )
        for k in CTX_IDS:  # carry id params forward for the next call
            if kwargs.get(k) is not None:
                st.session_state.ctx[k] = kwargs[k]
        _persist()
        st.rerun()


# --------------------- Transcript (the trajectory) ----------------------- #


st.divider()
st.subheader("Trajectory")

if not st.session_state.transcript:
    st.info("No calls yet. Every tool call you make is recorded here and logged to JSONL.")
else:
    n_load = sum(1 for r in st.session_state.transcript if r["load_bearing"])
    st.caption(f"{len(st.session_state.transcript)} call(s) · {n_load} marked load-bearing")
    last_seq = len(st.session_state.transcript)
    for rec in reversed(st.session_state.transcript):
        seq = rec["seq"]
        param_str = ", ".join(f"{k}={v!r}" for k, v in rec["params"].items())
        status = "✓" if rec["ok"] else "✗"
        with st.expander(f"#{seq} {status} {rec['tool']}({param_str})", expanded=(seq == last_seq)):
            lb = st.checkbox(
                "load-bearing (supported the final answer)",
                value=rec["load_bearing"],
                key=f"lb_{seq}",
            )
            if lb != rec["load_bearing"]:
                rec["load_bearing"] = lb
                _persist()
            if not rec["ok"]:
                st.error(rec["error"])
            else:
                _render_result(rec)
