#!/usr/bin/env bash
# Build the vendored mssql-mcp image that bundles.yaml's `mssql-mcp` MCP entry runs.
#
# Runs from any cwd — the build context is resolved from this script's own location.
# Override the tag with IMAGE=... ./build.sh (default: indie-marketplace-mssql-mcp:local,
# which is the tag hardcoded in bundles.yaml).
set -euo pipefail

IMAGE="${IMAGE:-indie-marketplace-mssql-mcp:local}"
context="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "==> docker build -t ${IMAGE} ${context}"
docker build -t "${IMAGE}" "${context}"

echo "==> built ${IMAGE}"
docker image inspect "${IMAGE}" --format '    id:      {{.Id}}
    created: {{.Created}}
    size:    {{.Size}} bytes'
