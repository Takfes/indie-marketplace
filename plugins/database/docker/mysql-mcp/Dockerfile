# Pinned wrapper around benborla/mcp-server-mysql — no image is published upstream, so
# this vendors their own multi-stage Dockerfile logic, frozen to a specific commit so an
# upstream change can't silently change what `docker build` produces.
#
# Pinned commit: b9c714e182422b9f18437242b80cf003adf1c7ea
# Source: https://github.com/benborla/mcp-server-mysql/blob/main/Dockerfile
#
# Build once locally:
#   plugins/database/docker/mysql-mcp/build.sh
#
# PUBLISHED multi-arch (linux/amd64 + linux/arm64) as:
#   takfes/indie-marketplace-mysql-mcp:b9c714e
# bundles.yaml consumes that tag directly; docker pulls it on first use.
# build.sh above builds a local :local tag for development only.
#
# To republish after bumping the pinned commit below (one-time builder setup:
#   docker buildx create --name multiarch --driver docker-container --use --bootstrap):
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -t takfes/indie-marketplace-mysql-mcp:<new-short-sha> \
#     --push plugins/database/docker/mysql-mcp
# Verify with: docker manifest inspect <that tag>  (expect both platforms)

FROM node:22-alpine AS source
RUN apk add --no-cache git
RUN git clone https://github.com/benborla/mcp-server-mysql.git /src \
    && cd /src && git checkout b9c714e182422b9f18437242b80cf003adf1c7ea

FROM node:22-alpine AS builder
RUN npm install -g pnpm
WORKDIR /app
COPY --from=source /src/package.json /src/pnpm-lock.yaml* /app/
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY --from=source /src /app
RUN pnpm run build

FROM node:22-alpine
RUN npm install -g pnpm
WORKDIR /app
COPY --from=builder /app/dist /app/dist
COPY --from=builder /app/package.json /app/
COPY --from=builder /app/pnpm-lock.yaml* /app/

# Upstream's own defaults (ALLOW_INSERT/UPDATE=true) — bundles.yaml's mysql-mcp
# entry overrides them to false via `docker run -e`, which is the real safety
# mechanism.
ENV MYSQL_HOST=127.0.0.1
ENV MYSQL_PORT=3306
ENV MYSQL_USER=root
ENV MYSQL_PASS=
ENV MYSQL_DB=db_name
ENV ALLOW_INSERT_OPERATION=true
ENV ALLOW_UPDATE_OPERATION=true
ENV ALLOW_DELETE_OPERATION=false

RUN pnpm install --prod --frozen-lockfile --ignore-scripts

ENTRYPOINT ["node", "dist/index.js"]
