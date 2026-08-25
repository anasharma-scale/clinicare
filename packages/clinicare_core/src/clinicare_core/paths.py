"""Repo layout, derived from the location of the file that asks for it.

The eval scripts import one another as flat modules (`from insight_grounding import …`) and also
reach into `benchmark/_template/tests/` for the scorer the trial container runs. Both need
directories on `sys.path`. This is the one spelling for that, with no depth arithmetic to get
wrong when a file moves between `eval/gold/` and `eval/metrics/grounding/`.

WHY THE PATH IMPORTS CAN'T JUST GO AWAY. `benchmark/_template/tests/{judge,evidence,policy_scoring}.py`
are copied into every trial container and run there as `python3 judge.py` with no package
installed and no third-party dependencies. That zero-dependency property is what makes the
outcome score credential-free and reproducible, so those modules cannot import a workspace
package — which means the eval side has to reach them by path. The dependency runs one way:
eval may import the container code, never the reverse.

WHY THIS IS IN AN INSTALLED PACKAGE AND `env_image.py` IS NOT. Everything here navigates from
the CALLER's location, never from this module's own. An installed package genuinely cannot know
where the repo is; `env_image.py` content-hashes files at fixed repo paths, so it stays in the
source tree where its own `__file__` is meaningful.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Layout:
    """Absolute paths to the directories eval modules import from."""

    root: Path
    benchmark: Path
    eval: Path
    core: Path
    gold: Path
    metrics: Path
    grounding: Path
    reliability: Path
    report: Path
    scripts: Path
    construction: Path
    #: benchmark/_template/tests — the code that also runs inside the trial container.
    container_tests: Path


def find_repo_root(start: Path) -> Path:
    """Nearest ancestor of `start` that looks like this repo.

    Keyed on the two top-level directories rather than a marker file, so a stray pyproject.toml
    or .git inside a subtree can't produce a plausible-but-wrong root.
    """
    start = Path(start).resolve()
    for d in (start, *start.parents):
        if (d / "benchmark").is_dir() and (d / "packages").is_dir():
            return d
    raise RuntimeError(
        f"could not locate the CliniCARE repo root above {start} "
        "(looked for a directory containing both benchmark/ and packages/)"
    )


def layout(caller_file: str | Path) -> Layout:
    """The repo layout, resolved from any file inside the repo. Pass `__file__`."""
    root = find_repo_root(Path(caller_file).parent)
    benchmark = root / "benchmark"
    ev = benchmark / "eval"
    return Layout(
        root=root,
        benchmark=benchmark,
        eval=ev,
        core=ev / "core",
        gold=ev / "gold",
        metrics=ev / "metrics",
        grounding=ev / "metrics" / "grounding",
        reliability=ev / "reliability",
        report=ev / "report",
        scripts=benchmark / "scripts",
        construction=root / "construction",
        container_tests=benchmark / "_template" / "tests",
    )


def bootstrap(caller_file: str | Path, *names: str) -> Layout:
    """Put the named layout directories on `sys.path` and return the layout.

    `bootstrap(__file__, "grounding", "container_tests")` replaces a stack of hand-rolled
    `sys.path.insert` lines. Names are Layout field names; an unknown one raises rather than
    silently leaving the import to fail later with a confusing ModuleNotFoundError. Directories
    are prepended in the order given and never duplicated.
    """
    lay = layout(caller_file)
    for name in names:
        try:
            d = getattr(lay, name)
        except AttributeError:
            raise AttributeError(
                f"unknown layout directory {name!r}; known: "
                + ", ".join(f.name for f in lay.__dataclass_fields__.values())
            ) from None
        s = str(d)
        if s not in sys.path:
            sys.path.insert(0, s)
    return lay
