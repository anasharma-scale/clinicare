#!/usr/bin/env bash
# Build the trial container image. Run this once, and again after any change to
# benchmark/_template/environment/Dockerfile or packages/mimic_tools/ — those are the image's
# content-hash inputs, so a change there changes the tag build_tasks.py expects.
#
#   bash scripts/build_image.sh                                   # local image (the default)
#   CLINICARE_IMAGE_REPO=ghcr.io/you/clinicare-env \
#     bash scripts/build_image.sh --push                          # build and push to a registry
#   MIMIC_ENV_TAG=v1 bash scripts/build_image.sh                  # explicit tag instead of the hash
#   PLATFORMS=linux/amd64,linux/arm64 bash scripts/build_image.sh --push   # multi-arch (push only)
#
# The tag comes from benchmark/scripts/env_image.py, which derives `src-<hash>` from the exact
# build inputs — the same value build_tasks.py bakes into each task's docker_image. So there is
# no version to bump and no way for the tasks and the image to disagree.
#
# A LOCAL image is enough to run trials: the agent container and the mimic-tools sidecar are the
# same image with different commands, and Docker runs it straight from your daemon. You only need
# a registry if a remote backend has to pull it.
#
# One quirk worth knowing: multi-platform builds cannot be loaded into the local daemon, only
# pushed. So --platform is honoured for --push and ignored otherwise, where the build is native.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# The Dockerfile lives with the task template (Harbor's convention: a task's environment is
# defined there), but the build CONTEXT is packages/mimic_tools so the image's COPYs resolve.
DOCKERFILE="${ROOT}/benchmark/_template/environment/Dockerfile"
CONTEXT_DIR="${ROOT}/packages/mimic_tools"

PUSH=0
[ "${1:-}" = "--push" ] && PUSH=1

command -v docker >/dev/null || { echo "docker not on PATH" >&2; exit 1; }

IMAGE_REF="$(python3 "${ROOT}/benchmark/scripts/env_image.py" --ref)"
PLATFORMS="${PLATFORMS:-linux/amd64}"

yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }

if [ "$PUSH" -eq 1 ]; then
    # buildx with the docker-container driver: the default `docker` driver supports neither
    # multi-platform nor --push.
    BUILDER="${BUILDX_BUILDER:-clinicare-builder}"
    if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
        yellow "→ Creating buildx builder ${BUILDER} (docker-container driver)"
        docker buildx create --name "$BUILDER" --driver docker-container --bootstrap >/dev/null
    fi
    yellow "→ Building + pushing ${IMAGE_REF}  [${PLATFORMS}]"
    docker buildx build --builder "$BUILDER" --platform "$PLATFORMS" \
        -f "$DOCKERFILE" -t "$IMAGE_REF" --push "$CONTEXT_DIR"
    green "✓ Pushed ${IMAGE_REF}"
else
    yellow "→ Building ${IMAGE_REF} (native arch, into the local daemon)"
    docker build -f "$DOCKERFILE" -t "$IMAGE_REF" "$CONTEXT_DIR"
    green "✓ Built ${IMAGE_REF}"
fi

green "  build_tasks.py resolves this ref automatically (benchmark/scripts/env_image.py)."
