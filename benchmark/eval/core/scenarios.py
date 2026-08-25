"""Scenario identity, derived from ``benchmark/_scenarios/`` — the source of truth.

Several points in the eval pipeline have to answer the same question, "which scenario is this?",
from a different starting point:

  * a trial dir named ``<scenario-id>-<6hex task id>__<trial suffix>``
  * an annotation row titled ``Task N — ...``
  * a scenario id on its own

The numbering is ours: ``_scenarios/`` dirs are ``scenario-NN-<name>`` and the annotation's
``Task N`` follows that NN. Because the correspondence is derivable, nothing here is hand-listed —
adding or renumbering a scenario updates every consumer at once, and a dir that breaks the naming
convention fails loudly instead of silently dropping a scenario from a gold build or a metric.
"""

from __future__ import annotations

import re
import sys
import tomllib
from functools import lru_cache

from clinicare_core.paths import layout

_DIR_RE = re.compile(r"^scenario-(\d+)-")
_TITLE_RE = re.compile(r"^\s*Task\s+(\d+)\b")
# Task ids are `<scenario-id>-<HASH_LEN hex>`; scenario ids contain hyphens, so strip the
# known-width hash rather than splitting on "-".
_TASK_SUFFIX_RE = re.compile(r"-[0-9a-f]{6}$")


@lru_cache(maxsize=1)
def task_by_slug() -> dict[str, int]:
    """{scenario id: task number}, read off the ``scenario-NN-`` dir prefixes."""
    scenarios = layout(__file__).benchmark / "_scenarios"
    out: dict[str, int] = {}
    seen: dict[int, str] = {}
    for d in sorted(scenarios.iterdir()):
        toml = d / "scenario.toml"
        if not toml.is_file():
            continue
        m = _DIR_RE.match(d.name)
        if not m:
            sys.exit(
                f"scenario dir {d.name!r} has no `scenario-NN-` prefix — the task number is read "
                f"from it, so an unnumbered dir would silently drop out of the gold builds."
            )
        n = int(m.group(1))
        if n in seen:
            sys.exit(f"duplicate scenario number {n}: {seen[n]!r} and {d.name!r}")
        seen[n] = d.name
        out[tomllib.loads(toml.read_text())["id"]] = n
    return out


@lru_cache(maxsize=1)
def slug_by_task() -> dict[int, str]:
    """{task number: scenario id} — the inverse of :func:`task_by_slug`."""
    return {n: s for s, n in task_by_slug().items()}


def task_from_title(title: str) -> int | None:
    """The N in an annotation title like ``Task 6 — ICU sepsis-bundle (SEP-1) compliance``."""
    m = _TITLE_RE.match(title or "")
    return int(m.group(1)) if m else None


def slug_from_trial_dir(name: str) -> str | None:
    """Scenario id from a trial dir name, or None if it matches no known scenario.

    The scenario is not its own path component in a harbor job dir — it is encoded in the trial
    dir name, ``<scenario-id>-<6hex>__<trial>``.
    """
    known = set(task_by_slug())
    stem = name.split("__")[0]
    if stem in known:
        return stem
    stripped = _TASK_SUFFIX_RE.sub("", stem)
    if stripped in known:
        return stripped
    # Last resort: the longest scenario id that prefixes the name. Guards against a change to the
    # task-id width without silently matching nothing.
    cands = [k for k in known if stem.startswith(k)]
    return max(cands, key=len) if cands else None
