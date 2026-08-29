#!/usr/bin/env bash
# build.sh - build and tag the vendored mysql-mcp image used by bundles.yaml.
# Usage: plugins/database/docker/mysql-mcp/build.sh   (runs from any cwd)
#
# Produces indie-marketplace-mysql-mcp:local for DEVELOPMENT. bundles.yaml's
# `mysql-mcp` entry consumes the published multi-arch
# takfes/indie-marketplace-mysql-mcp tag, which docker pulls on first use.
# See the Dockerfile header for the buildx command that republishes it. The build context is this script's own directory, so the
# vendored Dockerfile here is the only input. See VERIFIED.md for the smoke test
# and the eventual Docker Hub name.
set -euo pipefail

IMAGE="indie-marketplace-mysql-mcp:local"
CONTEXT="$(cd "$(dirname "$0")" && pwd)"

echo "building $IMAGE from $CONTEXT"
docker build -t "$IMAGE" "$CONTEXT"

echo "built $IMAGE ($(docker image inspect -f '{{.Id}}' "$IMAGE"))"
