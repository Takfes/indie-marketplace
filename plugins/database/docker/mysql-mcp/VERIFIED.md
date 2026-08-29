# mysql-mcp image — local verification

Evidence for [issue #83](https://github.com/Takfes/indie-marketplace/issues/83): the
vendored `mysql-mcp` image builds, answers a real query, and the app-level write gate
in `bundles.yaml` actually holds.

Verified 2026-08-29 against upstream commit `b9c714e182422b9f18437242b80cf003adf1c7ea`.

## Build

```
$ plugins/database/docker/mysql-mcp/build.sh
building indie-marketplace-mysql-mcp:local from .../plugins/database/docker/mysql-mcp
...
#17 writing image sha256:042fc530ba9b6298b034a201eff27ace5e9f3398cb35d09e2f45855b0a592b41
#17 naming to docker.io/library/indie-marketplace-mysql-mcp:local
built indie-marketplace-mysql-mcp:local (sha256:042fc530ba9b6298b034a201eff27ace5e9f3398cb35d09e2f45855b0a592b41)
```

Image id `sha256:042fc530ba9b…`, 507 MB. Built from a clean checkout of this branch;
no local digest exists yet because nothing has been pushed.

## Test target

The throwaway `stack-database-mcp` compose stack (`mysql:8`, host port 3306, seeded
from its `init/mysql-seed.sql`: `products`, `inventory`). Its credentials are the
public test defaults published in that project's committed `docker-compose.yml` — not
secrets, and deliberately not duplicated here. `MYSQL_MCP_HOST` is
`host.docker.internal` so the MCP container reaches the DB through the host port.

The DB user is `root` — full grants. MySQL will **not** refuse any of the writes below.
That isolates the app-level gate as the only thing standing in the way.

## Smoke test — `tools/list` and a real SELECT

Driven over MCP stdio with exactly the `docker run` invocation `bundles.yaml` uses,
including the three `ALLOW_*_OPERATION=false` flags:

```
docker run -i --rm \
  -e MYSQL_HOST=host.docker.internal -e MYSQL_USER=... -e MYSQL_PASS=... -e MYSQL_DB=appdb \
  -e ALLOW_INSERT_OPERATION=false \
  -e ALLOW_UPDATE_OPERATION=false \
  -e ALLOW_DELETE_OPERATION=false \
  indie-marketplace-mysql-mcp:local
```

`initialize` returns `serverInfo: {"name":"MySQL MCP Server","version":"1.0.0"}`.
`tools/list` returns exactly one tool:

```json
{"name":"mysql_query","description":"[MySQL MCP Server [vundefined]] Run SQL queries against MySQL database (READ-ONLY)",
 "inputSchema":{"type":"object","properties":{"sql":{"type":"string"}},"required":["sql"]},
 "annotations":{"readOnlyHint":true,"idempotentHint":true,"destructiveHint":false,"openWorldHint":false,"title":"MySQL Query"}}
```

Request:

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"mysql_query","arguments":{
  "sql":"SELECT p.id, p.name, p.price, i.quantity FROM products p JOIN inventory i ON i.product_id = p.id ORDER BY p.id"}}}
```

Response (`isError: false`):

```json
[
  { "id": 1, "name": "Widget", "price": "9.99",  "quantity": 100 },
  { "id": 2, "name": "Gadget", "price": "24.50", "quantity": 40  },
  { "id": 3, "name": "Gizmo",  "price": "5.00",  "quantity": 250 }
]
```
plus `"Query execution time: 24.28 ms"`.

## Write gate — held on all three operations

Same session, same flags. Each request and its verbatim response:

| # | Request `sql` | Response `content[0].text` | `isError` |
|---|---|---|---|
| 3 | `INSERT INTO products (name, price) VALUES ('WriteGateProbe', 1.00)` | `Error: INSERT operations are not allowed for schema 'appdb'. Ask the administrator to update SCHEMA_INSERT_PERMISSIONS.` | `true` |
| 4 | `UPDATE products SET price = 999.99 WHERE id = 1` | `Error: UPDATE operations are not allowed for schema 'appdb'. Ask the administrator to update SCHEMA_UPDATE_PERMISSIONS.` | `true` |
| 5 | `DELETE FROM inventory WHERE id = 3` | `Error: DELETE operations are not allowed for schema 'appdb'. Ask the administrator to update SCHEMA_DELETE_PERMISSIONS.` | `true` |

Database state before and after the probe was byte-identical (3 rows in `products`,
3 rows in `inventory`, prices unchanged). **Nothing landed.**

### Adjacent probes — no leak found

Not required by the issue, but the obvious bypasses were tried in the same
configuration:

| Request `sql` | Response |
|---|---|
| `CREATE TABLE write_gate_probe (id INT)` | `Error: DDL operations are not allowed for schema 'appdb'. …SCHEMA_DDL_PERMISSIONS.` |
| `SELECT 1 AS ok; INSERT INTO products (name, price) VALUES ('StackedProbe', 2.00)` | `Error: INSERT operations are not allowed for schema 'appdb'. …` |
| `TRUNCATE TABLE inventory` | `Error: DDL operations are not allowed for schema 'appdb'. …` |
| `DROP TABLE IF EXISTS write_gate_probe` | `Error: DDL operations are not allowed for schema 'appdb'. …` |

The stacked-statement case matters most: the leading `SELECT` does not smuggle the
trailing `INSERT` past the parser. `SHOW TABLES` afterwards still listed only
`inventory` and `products`.

### Where the rejection happens

At the **MCP layer**, before MySQL is asked. Three things establish that:

1. The error strings are upstream's own (`SCHEMA_*_PERMISSIONS`), not a MySQL error
   code — MySQL never produced a diagnostic.
2. The connected user is `root`, so MySQL would have accepted every statement.
3. **Control test.** The same image, same SQL, with only `ALLOW_INSERT_OPERATION`
   flipped to the image's own default `true`:

   ```
   >>> {"method":"tools/call","params":{"name":"mysql_query","arguments":{
         "sql":"INSERT INTO products (name, price) VALUES ('ControlProbe', 1.00)"}}}
   <<< {"result":{"content":[{"type":"text","text":
         "Insert successful on schema 'appdb'. Affected rows: 1, Last insert ID: 4"}],"isError":false}}
   ```

   The row **did** land (`id=4, ControlProbe, 1.00`) and was then removed directly via
   `mysql` in the DB container (`DELETE FROM products WHERE name='ControlProbe';
   ALTER TABLE products AUTO_INCREMENT=4;`) — `products` is back to its seeded 3 rows.

   That is the point of the control: the `ALLOW_*_OPERATION=false` flags in
   `bundles.yaml` are the *only* thing preventing the write. Remove them and writes
   go through immediately. Consistent across all three operations, no leak.

Consequence worth remembering: the gate is per-`docker run`, not baked into the image.
Anyone invoking this image outside `bundles.yaml` gets the upstream defaults —
`ALLOW_INSERT_OPERATION=true`, `ALLOW_UPDATE_OPERATION=true` — and can write.

## Eventual Docker Hub name/tag

Decision: **`takfes/indie-marketplace-mysql-mcp:b9c714e`** — not published; pushing is
out of scope for #83.

- Namespace `takfes` matches the GitHub owner of this marketplace (Docker Hub
  namespaces are lowercase).
- Repository name keeps the `indie-marketplace-mysql-mcp` string already in use, so the
  `:local` tag and the published one differ only by the registry prefix.
- Tag is the short upstream commit SHA the Dockerfile pins. That commit is the only
  thing that determines the image contents, so the tag is immutable and self-documenting
  — re-pinning upstream means a new tag, never a silently changed one. A `:latest`
  alias may be pushed alongside it, but `bundles.yaml` should always name the SHA tag.

Swap diff once it is pushed — one line in `bundles.yaml`'s `mysql-mcp` entry:

```diff
-            "indie-marketplace-mysql-mcp:local",
+            "takfes/indie-marketplace-mysql-mcp:b9c714e",
```

`build.sh` and the Dockerfile keep building the `:local` tag for development; the
published tag is only what consumers pull.
