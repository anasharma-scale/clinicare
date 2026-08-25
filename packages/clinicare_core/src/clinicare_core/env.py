"""Read the repo-root `.env`, with the real environment taking precedence.

Replaces three near-identical copies that had drifted apart on exactly the question of who
wins. They now all use this one, whose rule is the least surprising of the three: **a real
environment variable always beats the file.** (One of the originals ignored the process
environment entirely; another honoured it for three hardcoded keys.) So
`JUDGE_MODEL=... python ...` overrides `.env` everywhere, as you would expect.

`root` is passed in rather than derived from `__file__` — this module lives in an installed
package, so its own location says nothing about where the repo is. Callers already compute
their own repo root; they pass it. Omitting it walks up from the current directory instead.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_LINE = re.compile(r"\s*([A-Z_][A-Z0-9_]*)=(.*)")
_INTERP = re.compile(r"\$\{(\w+)\}")
# Markers of the repo root, in priority order, for the no-argument case.
_ROOT_MARKERS = (".env", "pyproject.toml", ".git")


def find_root(start: Path | None = None) -> Path | None:
    """Nearest ancestor of `start` (default: cwd) that looks like the repo root."""
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if any((d / m).exists() for m in _ROOT_MARKERS):
            return d
    return None


def load_env(root: Path | None = None) -> dict[str, str]:
    """`.env` values merged under the process environment, with `${VAR}` references expanded.

    Returns the full merged mapping (process environment included), so callers can `.get()` a
    key whether it came from the file or the shell. A missing `.env` is fine — you just get the
    process environment back.
    """
    root = root or find_root()
    parsed: dict[str, str] = {}
    envfile = (root / ".env") if root else None
    if envfile and envfile.is_file():
        for line in envfile.read_text().splitlines():
            if line.lstrip().startswith("#"):
                continue
            m = _LINE.match(line)
            if m:
                parsed[m.group(1)] = m.group(2).strip()

        # Expand against the file's own values first, then the process environment, so a
        # `.env` line like JUDGE_API_KEY=${OPENAI_API_KEY} resolves either way.
        def expand(v: str) -> str:
            return _INTERP.sub(lambda x: parsed.get(x.group(1), os.environ.get(x.group(1), "")), v)

        parsed = {k: expand(v) for k, v in parsed.items()}
    return {**parsed, **os.environ}
