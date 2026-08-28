---
name: secrets-manager
description: Launch the local credential-editing UI for indie-marketplace profiles, or answer configuration questions without ever reading a value — which variables are unset, which profile a directory resolves to and why, and a doctor check for stale bound paths, orphaned variables, and bad store permissions. Use when the user asks to open/launch the secrets manager, edit credentials or API keys, check what's configured or unconfigured, ask which profile applies to a project, or wants a health check on their credential profiles.
---

# Secrets Manager

Everything below except **Launch** answers questions from catalog variable
names, profile state labels, project paths, and file permissions — never a
credential value. Launch itself never touches a value either: it starts a
server and relays one URL. Reading, editing, and revealing values only ever
happens in the user's own browser, driven by their own clicks.

## Launch

Start the server bundled with this skill and hand the user its URL:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/secrets-manager/server.py"
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
python3 "${CLAUDE_PLUGIN_ROOT}/skills/secrets-manager/status.py" unset [--profile NAME]
```

Lists every catalog-declared variable that's unset for a profile (default:
whichever profile the current directory resolves to — see below), tagged
required/optional. Use when the user asks what's missing or unconfigured.

## Which profile applies here

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/secrets-manager/status.py" resolve [PATH]
```

Reports which profile a directory (default: cwd) resolves to and why:
`$INDIE_PROFILE`, a bound project path, the `active` file, or the `base`
fallback — in that precedence order.

## Doctor

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/secrets-manager/status.py" doctor
```

Reports three kinds of drift: profiles whose bound project paths no longer
exist on disk, variables stored in `profiles.json` that no installed plugin
declares anymore, and store files/directory whose permissions aren't
`0600`/`0700`.

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
