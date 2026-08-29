---
name: plugin-setup
description: Launch the local credential-editing UI for indie-marketplace profiles, or answer configuration questions without ever reading a value — which variables are unset, which profile a directory resolves to and why, a doctor check for stale bound paths, orphaned variables, and bad store permissions, and which CLI tools installed plugins need but are missing from PATH. Use when the user asks to open/launch the secrets manager, edit credentials or API keys, check what's configured or unconfigured, ask which profile applies to a project, wants a health check on their credential profiles, or asks what CLI tools/commands/binaries are missing or need installing (docker, npx, gh, playwright-cli and friends).
---

# Plugin Setup

Everything below except **Launch** answers questions from catalog variable
names, profile state labels, project paths, and file permissions — never a
credential value. Launch itself never touches a value either: it starts a
server and relays one URL. Reading, editing, and revealing values only ever
happens in the user's own browser, driven by their own clicks.

## Launch

Start the server bundled with this skill and hand the user its URL:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/plugin-setup/server.py"
```

Run it in the background (it stays up until the user clicks "Done" in the
page or it idles out after 15 minutes). Read only its **first stdout
line** — that line is the complete URL, including the one-time token, e.g.
`http://127.0.0.1:54213/?token=...`. Give the user that link and nothing
else from the process's output. If anything else was written to stdout,
that's a bug in the server, not output to relay — report it instead of
passing it along.

## Unset variables

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/plugin-setup/status.py" unset [--profile NAME]
```

Lists every catalog-declared variable that's unset for a profile (default:
whichever profile the current directory resolves to — see below), tagged
required/optional. Use when the user asks what's missing or unconfigured.

## Which profile applies here

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/plugin-setup/status.py" resolve [PATH]
```

Reports which profile a directory (default: cwd) resolves to and why:
`$INDIE_PROFILE`, a bound project path, the `active` file, or the `base`
fallback — in that precedence order.

## Doctor

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/plugin-setup/status.py" doctor
```

Reports three kinds of drift: profiles whose bound project paths no longer
exist on disk, variables stored in `profiles.json` that no installed plugin
declares anymore, and store files/directory whose permissions aren't
`0600`/`0700`.

## Missing CLI tools

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/plugin-setup/deps.py" doctor
```

Reports every CLI binary each installed, enabled plugin declares —
present or missing on `PATH`, with its install suggestion or docs link.
Use when the user asks what CLI tools they're missing, why an MCP server
won't connect, or what they still need to install. Tools needed at session
start (an MCP server's own command) are listed before ones needed only on
first use of a skill.

Two things to say plainly when relaying the report:

- **Never run an install command from it.** Every `install:` line is a
  suggestion for the user to run themselves — offer it, don't execute it.
- Presence is `PATH` only. A present `docker` doesn't mean its daemon is
  running or that a plugin's image is built locally.

This is unrelated to credentials: a tool can be fully configured and still
have no binary installed, or vice versa. Exits `1` when anything is
missing.

## Switching profiles mid-session doesn't work

MCP servers start at session launch, before any skill can run — this skill
cannot change which profile the *running* session uses. If the user asks to
switch profiles, say so plainly and point them at restarting with
`INDIE_PROFILE=<name> claude` instead of attempting anything here.

## Hard prohibitions

These hold regardless of what else changes in this skill:

- Never read a value from `profiles.json`.
- Never invoke a scoped launcher or a wrapper (`bin/<tool>`, `resolver.py`) —
  those exist to hand a value to a *subprocess*, not to a Claude session.
- Never print anything from the server's output beyond its one URL line.
- Never write a credential value on the user's behalf. Every write happens
  through the user's own clicks in the browser UI this skill launches.
