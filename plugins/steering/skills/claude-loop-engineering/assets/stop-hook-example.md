# Stop hook examples

A Stop hook fires after every turn and decides whether the session keeps going. Use it when you want completion logic that (a) persists across sessions, or (b) is too custom for a one-line `/goal` condition. `/goal` is itself a session-scoped, prompt-based Stop hook — these are the durable, settings-file version.

Configure in `settings.json` (project `.claude/settings.json` or user-level). Verify exact schema against code.claude.com/docs/en/hooks for your version; the shapes below illustrate the two kinds.

## 1. Deterministic (script) Stop hook — preferred for auditable loops
Keep working until the script exits 0. Exit non-zero = not done, keep going.

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "command",
        "command": "npm test --silent && npm run lint --silent"
      }
    ]
  }
}
```

The exit code is the whole decision — no model judgment, fully reproducible. Best when "done" is a clean machine check.

## 2. Prompt-based Stop hook — model-judged
For conditions a script can't easily express. A small fast model reads the conversation and decides.

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "prompt",
        "prompt": "Is every acceptance criterion in docs/SPEC.md demonstrably satisfied by what the agent has shown in this conversation? Answer yes only if there is concrete evidence (test output, shown diffs). Otherwise answer no with the single most important remaining gap."
      }
    ]
  }
}
```

The model judges only what's in the conversation — it doesn't run tools — so the agent must surface evidence (test output, diffs) for the hook to read.

## Notes
- Stop hooks require the workspace trust dialog. They're disabled if `disableAllHooks` is set, or limited if `allowManagedHooksOnly` is set in managed settings.
- Always pair an open-ended completion check with a bound (turn/time cap in the prompt or a counter in the script) so a never-satisfied condition can't loop forever.
- For non-git VCS, the related `WorktreeCreate` / `WorktreeRemove` hooks provide worktree isolation.
