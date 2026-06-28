# indie-marketplace

Personal Claude Code skill marketplace. All plugins are defined in `bundles.yaml` and built by `build.py`.

## Structure

```
bundles.yaml        ← config: skills → plugins (edit this)
build.py            ← build script (run this)
marketplace.json    ← generated manifest (commit after build)
skills/             ← canonical source for custom skills (edit freely)
plugins/            ← built output (commit after build)
```

## Workflows

**Add a custom skill to a plugin**

1. Put the skill directory in `skills/<name>/`
2. Add an entry under the plugin in `bundles.yaml` with `source: local`
3. Run `make build`

**Add a community skill to a plugin**

1. Find the GitHub repo containing the skill
2. Add an entry in `bundles.yaml` with `source: community`, `repo:`, and `path:`
3. Run `make fetch` (clones repo and copies skill into plugin)

**Add a new plugin**

1. Add a new block under `plugins:` in `bundles.yaml`
2. Run `make build`

**Command reference**

| Command | What it does |
|---|---|
| `make build` | Build all plugins using cached community skills |
| `make fetch` | Re-download all community skills (no build) |
| `make fetch-build` | Re-download community skills, then build everything |
| `make build provision` | Build one plugin, use cache |
| `make fetch provision` | Re-download community skills for one plugin only |
| `make fetch-build provision` | Re-download + build one plugin |

## Publishing

Push this repo to GitHub. Add it as a marketplace in Claude Code:

```
/plugin marketplace add Takfes/indie-marketplace
```

Install a plugin (the `@indie-marketplace` qualifier identifies which marketplace to use):

```
/plugin install provision@indie-marketplace
```
