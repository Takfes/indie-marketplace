# Pinned wrapper around JexinSam/mssql_mcp_server — no image is published upstream, so
# this vendors their Dockerfile logic, frozen to a specific commit. Also fixes a real
# upstream bug as a proper build step instead of a runtime sed patch: their Dockerfile
# never copies README.md into the build context, but pyproject.toml's hatchling backend
# requires it, so `pip install .` fails on a stock clone.
#
# Pinned commit: ef13c17be6c270be9ebc07ebb621d0bc1901e4e9
# Source: https://github.com/JexinSam/mssql_mcp_server/blob/main/Dockerfile
#
# Build once locally:
#   docker build -t indie-marketplace-mssql-mcp:local plugins/integrations/docker/mssql-mcp

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
