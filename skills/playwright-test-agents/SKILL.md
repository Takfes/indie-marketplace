---
name: playwright-test-agents
description: |
  Set up and use Playwright's official Planner/Generator/Healer test agents for self-healing Playwright end-to-end test authoring with @playwright/test. Use this skill when the user wants to write E2E/Playwright tests from scratch, explore a running app to produce a test plan, turn a test plan into runnable Playwright test files, or automatically diagnose and fix failing Playwright tests. Also trigger on "playwright agents", "test plan", "self-healing tests", "heal this test", or a request to plan/generate/heal an E2E suite. Do NOT trigger for one-off manual browser actions, scraping, or ad hoc codegen with no test-authoring intent — use the playwright-cli skill for that instead.
allowed-tools:
  - Bash(npx playwright *)
  - Bash(npm init playwright*)
---

# Playwright Test Agents (Planner / Generator / Healer)

Official `@playwright/test` agent definitions for building and maintaining an E2E suite: **Planner** explores the running app and writes a human-readable test plan, **Generator** turns a reviewed plan into runnable Playwright TypeScript tests, and **Healer** diagnoses a failing test against the live app and repairs it.

## Setup

Requires an existing Playwright project — check for `playwright.config.ts`/`.js` first; if missing, bootstrap one:

```bash
npm init playwright@latest
```

Then generate the agent definitions for Claude Code:

```bash
npx playwright init-agents --loop=claude
```

This scaffolds:

- `.claude/agents/planner.md`, `generator.md`, `healer.md` — three subagents Claude Code can invoke directly by name once this command has run
- `specs/` — where the Planner writes test plans (e.g. `specs/checkout-flow.md`)
- `tests/seed.spec.ts` — the seed test every plan's scenarios start from
- `playwright.config.ts` if one didn't already exist

Safe to re-run any time `@playwright/test` is upgraded — agent definitions are versioned against the installed Playwright and can drift, so regenerate after every upgrade.

## Workflow

Invoke each agent by asking for it by name — Claude Code routes the request to the matching `.claude/agents/*.md` definition once `init-agents` has run:

1. **Plan** — "Use the planner agent to create a test plan for `<feature>`." Produces a Markdown plan under `specs/` with scenarios, steps, and expected outcomes. Review and edit the plan before generating.
2. **Generate** — "Use the generator agent to create tests from `specs/<feature>.md`." Walks the live app to verify locators and writes one test file per scenario.
3. **Heal** — "Use the healer agent to fix failing tests in `tests/<feature>/`." Re-inspects the live page for a failing test, repairs the locator/assertion, and reruns it. Point it at a specific file or the whole suite.

Run the three phases in order for a new feature; run only Heal on an existing suite after a UI change breaks tests.

## MCP dependency — heads-up

Each generated agent's own definition embeds calls into the Playwright MCP server (`@playwright/mcp`) for live DOM inspection — that's how the Generator verifies real locators and the Healer re-inspects a live page. This is scoped to *when that specific agent runs*, not a blanket addition to every session's tools: installing this `browser` plugin adds no MCP server of its own, and by default `npx` fetches `@playwright/mcp` on demand the first time an agent needs it.

If you want that server pre-installed and persistently configured instead of fetched on demand, install the separate `browser-mcp` plugin — it exists specifically for opt-in, live exploratory DOM control and pairs with these agents without either plugin depending on the other.

## Prefer no MCP dependency at all?

The `playwright-cli` skill (installed alongside this one) has its own CLI-driven plan → generate → heal workflow (see its `references/test-generation.md`) that uses only the `playwright-cli` binary and `npx playwright test --debug=cli` — no agent scaffolding, no MCP server. Reach for that instead when you want self-healing test authoring with zero MCP surface.
