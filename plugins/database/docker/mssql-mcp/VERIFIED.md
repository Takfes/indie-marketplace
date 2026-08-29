# mssql-mcp image — build & smoke-test record

Verified 2026-08-29 on macOS (darwin/arm64, Docker Desktop). Issue
[#82](https://github.com/Takfes/indie-marketplace/issues/82).

## Build

    plugins/database/docker/mssql-mcp/build.sh      # == docker build -t indie-marketplace-mssql-mcp:local <this dir>

Run from `/tmp` to prove the script is cwd-independent. Result:

    id:      sha256:0d6ba6e3dc51d46613076605b8d0945190365883630ec5c632970928b79ef1bb
    created: 2026-08-29T06:25:48Z
    size:    232738487 bytes

Upstream `JexinSam/mssql_mcp_server` @ `ef13c17be6c270be9ebc07ebb621d0bc1901e4e9`,
installed as `mssql_mcp_server-1.0.0` on `mcp 2.1.1` / `pyodbc 5.3.0` /
`msodbcsql18`. The vendored `COPY README.md` fix is what makes `pip install .`
succeed; without it hatchling fails on a stock clone.

## Smoke test

Driven as protocol-level MCP stdio — the same `docker run -i --rm -e …`
invocation `bundles.yaml` uses, with `initialize` → `notifications/initialized`
→ `tools/list` → `tools/call` piped to stdin. No Claude Code in the loop.

Target: the throwaway `stack-database-mcp` test stack (container
`stack-database-mcp-mssql-1`, `mcr.microsoft.com/mssql/server:2022-latest`, host
port 1433). The credentials are the public test defaults published in that
project's committed `docker-compose.yml` — not secrets, and deliberately not
duplicated here. `MSSQL_HOST` is `host.docker.internal` so the MCP container
reaches the DB through the host port.

    docker run -i --rm \
      -e TrustServerCertificate=yes \
      -e MSSQL_HOST=host.docker.internal \
      -e MSSQL_DATABASE=appdb \
      -e MSSQL_USER=... \
      -e MSSQL_PASSWORD=... \
      indie-marketplace-mssql-mcp:local

`tools/list` returned three tools: `list_tables`, `query_sql`, `execute_sql`.

`tools/call` with `query_sql`:

    {"query":"SELECT e.id, e.name, e.title, d.name AS department
              FROM employees e JOIN departments d ON d.employee_id = e.id
              ORDER BY e.id"}

Response, verbatim:

```json
{"jsonrpc":"2.0","id":3,"result":{"content":[{"text":"id,name,title,department\r\n1,Katherine Johnson,Mathematician,Flight Dynamics\r\n2,Margaret Hamilton,Software Engineer,Software Engineering\r\n3,Dorothy Vaughan,Programmer,Programming","type":"text"}],"isError":false,"structuredContent":{"result":"id,name,title,department\r\n1,Katherine Johnson,Mathematician,Flight Dynamics\r\n2,Margaret Hamilton,Software Engineer,Software Engineering\r\n3,Dorothy Vaughan,Programmer,Programming"}}}
```

That matches `init/mssql-seed.sql` exactly. Only SELECTs were issued; a
follow-up `SELECT id, title FROM employees WHERE id = 1` returned
`1,Mathematician`, confirming the stack was left untouched.

## Finding: TrustServerCertificate is required for dev/test servers

The first attempt failed at connect time:

    [08001] [Microsoft][ODBC Driver 18 for SQL Server]SSL Provider:
    [error:0A000086:SSL routines::certificate verify failed:self-signed certificate]

ODBC Driver 18 encrypts by default and upstream sets `TrustServerCertificate=no`
(a deliberate secure default as of their v1.0.0) — so this is correct behaviour
against a self-signed cert, not a bug in our image. Adding
`-e TrustServerCertificate=yes` fixed it.

`bundles.yaml`'s `mssql-mcp` entry passes no such flag, so **as configured today
it will fail against any SQL Server with a self-signed or internally-issued
certificate.** Left unchanged here on purpose — hardcoding `yes` would silently
disable cert validation for production targets too. Wiring it up as an optional
`${MSSQL_MCP_TRUST_SERVER_CERTIFICATE}` env var is a separate call.

## Finding: read-*mostly*, confirmed

The issue's characterisation is correct, verified against the pinned source in
the built image:

- `query_sql` gates on `^\s*(SELECT|WITH|SHOW)\b`. A `tools/call` with
  `UPDATE employees SET title = 'Hacked' WHERE id = 1` was rejected before
  reaching the database (`isError: true`); the row was re-read afterwards and
  still reads `Mathematician`.
- `execute_sql` has **no gate at all** — its own docstring advertises INSERT /
  UPDATE / DELETE / CREATE / ALTER / DROP, and it is annotated
  `destructiveHint: true`. There is no image- or config-level switch to turn it
  off, unlike `mysql-mcp`'s `ALLOW_*_OPERATION` flags.

So the only real write protection is the database grant. Point this MCP entry at
a read-only login (the test stack seeds an `mcp_readonly` login for exactly this)
rather than at `sa`.

## Docker Hub name/tag (decided, not published)

Pushing is out of scope for #82. Decision:

| Tag | Purpose |
| --- | --- |
| `takfes/indie-marketplace-mssql-mcp:ef13c17` | Immutable; short SHA of the pinned upstream commit. This is what `bundles.yaml` should reference. |
| `takfes/indie-marketplace-mssql-mcp:latest` | Moving convenience tag for humans. |

`takfes` mirrors the GitHub owner (`Takfes`, lowercased as Docker Hub requires);
the repo name mirrors the existing local tag so nothing else has to be renamed.
Tagging by upstream commit rather than a version of our own means bumping the
pin is a visible one-line diff instead of a silently-changed `:latest`.

The whole migration diff in `bundles.yaml` is one line:

```diff
-            "indie-marketplace-mssql-mcp:local",
+            "takfes/indie-marketplace-mssql-mcp:ef13c17",
```

`build.sh` still builds the `:local` tag for development; publishing would add
`docker tag` + `docker push` steps, not change the build.
