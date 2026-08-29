# Pinned wrapper around JexinSam/mssql_mcp_server — no image is published upstream, so
# this vendors their Dockerfile logic, frozen to a specific commit. Also fixes a real
# upstream bug as a proper build step instead of a runtime sed patch: their Dockerfile
# never copies README.md into the build context, but pyproject.toml's hatchling backend
# requires it, so `pip install .` fails on a stock clone.
#
# Pinned commit: ef13c17be6c270be9ebc07ebb621d0bc1901e4e9
# Source: https://github.com/JexinSam/mssql_mcp_server/blob/main/Dockerfile
#
# Build once locally (works from any cwd):
#   plugins/database/docker/mssql-mcp/build.sh
#
# PUBLISHED multi-arch (linux/amd64 + linux/arm64) as:
#   takfes/indie-marketplace-mssql-mcp:ef13c17   <- immutable, named for the pinned
#                                                   upstream commit below
# bundles.yaml consumes that tag directly; docker pulls it on first use and
# picks the right architecture. build.sh above is for development only.
#
# To republish after bumping the pinned commit below (one-time builder setup:
#   docker buildx create --name multiarch --driver docker-container --use --bootstrap):
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -t takfes/indie-marketplace-mssql-mcp:<new-short-sha> \
#     --push plugins/database/docker/mssql-mcp
# Verify with: docker manifest inspect <that tag>  (expect both platforms)
#
# Connecting to a server with a self-signed cert (any dev/test SQL Server) also
# needs `-e TrustServerCertificate=yes`: ODBC Driver 18 verifies by default and
# upstream deliberately leaves that default alone. bundles.yaml does not pass it.

FROM python:3.12-slim AS source
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/JexinSam/mssql_mcp_server.git /src \
    && cd /src && git checkout ef13c17be6c270be9ebc07ebb621d0bc1901e4e9

FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg2 \
        apt-transport-https \
        unixodbc-dev && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=source /src/pyproject.toml .
COPY --from=source /src/README.md .
COPY --from=source /src/src/ src/
RUN pip install --no-cache-dir .

ENV MSSQL_DRIVER="ODBC Driver 18 for SQL Server"
ENV MCP_TRANSPORT="stdio"

ENTRYPOINT ["mssql_mcp_server"]
