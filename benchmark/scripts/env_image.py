"""Single source of truth for the trial environment image ref.

Trials run in a prebuilt image (benchmark/_template/environment/Dockerfile, built from the
mimic_tools package) referenced by `docker_image` in each task.toml.

The tag is DERIVED from a content hash of the exact build inputs (the Dockerfile + the
mimic_tools source) rather than written down, so:
  * nothing is committed — build_tasks.py injects the ref at render time, so there is no line
    to merge-conflict on;
  * repo state is the image: change the Dockerfile or mimic_tools and the tag changes, and
    build_tasks' preflight fails loudly rather than silently using the wrong image.

Resolution order for the tag:
  1. $MIMIC_ENV_TAG if set — an explicit pin (e.g. to reproduce a specific published build);
  2. otherwise the content hash `src-<12hex>` of the build inputs.

WHERE THE IMAGE LIVES. $CLINICARE_IMAGE_REPO, default `clinicare-env` — a bare name, meaning a
LOCAL Docker image with no registry involved. Build it with `bash scripts/build_image.sh`; the
sidecar and the agent container both run it from your daemon. Set it to a registry path
(`ghcr.io/you/clinicare-env`) only if you need remote backends to pull it, in which case
build_image.sh will push.

  python benchmark/scripts/env_image.py --tag    # -> src-ab12cd34ef56 (or the pin)
  python benchmark/scripts/env_image.py --ref    # -> <repo>:<tag>
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent  # benchmark/scripts/
BENCHMARK = SCRIPTS.parent  # benchmark/
ROOT = SCRIPTS.parents[1]  # repo root (scripts → benchmark → root)
DOCKERFILE = BENCHMARK / "_template" / "environment" / "Dockerfile"
MIMIC_TOOLS = ROOT / "packages" / "mimic_tools"

# A bare name is a local-only image; anything with a registry host in front is pullable.
IMAGE_REPO = os.environ.get("CLINICARE_IMAGE_REPO", "clinicare-env")


def is_registry_ref(repo: str = "") -> bool:
    """True when the repo names a remote registry, i.e. its first path component looks like a
    host (contains a dot or a port). `clinicare-env` and `me/clinicare-env` are local;
    `ghcr.io/me/clinicare-env` and `localhost:5000/x` are not."""
    head = (repo or IMAGE_REPO).split("/")[0]
    return "/" in (repo or IMAGE_REPO) and ("." in head or ":" in head)


def _build_inputs() -> list[Path]:
    """Every file that goes INTO the image, in a stable order — the Dockerfile plus the
    mimic_tools sources it COPYs. Anything not here (e.g. this script) does not affect the tag."""
    files = [DOCKERFILE, MIMIC_TOOLS / "pyproject.toml", MIMIC_TOOLS / "README.md"]
    src = MIMIC_TOOLS / "src"
    if src.is_dir():
        files += [
            p
            for p in src.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
    return sorted((f for f in files if f.exists()), key=lambda p: str(p))


def content_tag() -> str:
    """`src-<12hex>` — sha256 over (repo-relative path, bytes) of each build input."""
    h = hashlib.sha256()
    for p in _build_inputs():
        h.update(p.relative_to(ROOT).as_posix().encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return "src-" + h.hexdigest()[:12]


def image_tag() -> str:
    return os.environ.get("MIMIC_ENV_TAG") or content_tag()


def image_ref() -> str:
    return f"{IMAGE_REPO}:{image_tag()}"


def _docker(*args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def tag_exists(tag: str) -> bool | None:
    """Is this image available to run?

    True/False when we could determine it; None when we could not (docker missing, daemon down,
    registry unreachable). Callers treat None as "unknown — warn but proceed" and hard-fail only
    on False, so a missing docker CLI never blocks a build that isn't going to run trials.

    A local image counts regardless of registry: `docker run` prefers what is already in the
    daemon. Only if it is absent locally AND the repo names a registry do we ask the registry.
    """
    ref = f"{IMAGE_REPO}:{tag}"
    local = _docker("image", "inspect", ref)
    if local is None:
        return None
    if local.returncode == 0:
        return True
    if not is_registry_ref():
        return False  # local-only repo, not in the daemon: definitively absent
    remote = _docker("manifest", "inspect", ref)
    if remote is None:
        return None
    if remote.returncode == 0:
        return True
    err = (remote.stderr or "").lower()
    if "manifest unknown" in err or "not found" in err:
        return False
    return None  # auth/network/other → unknown


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", action="store_true", help="print the resolved image tag")
    ap.add_argument("--ref", action="store_true", help="print the full <host>/<repo>:<tag> ref")
    args = ap.parse_args()
    print(image_tag() if args.tag else image_ref())
