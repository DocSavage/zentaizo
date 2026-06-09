---
created: 2026-06-08
status: implemented
implemented: 2026-06-09
edited_by:
  - 2026-06-08  Claude Opus 4.8 (1M context)
  - 2026-06-09  Claude Opus 4.8 (1M context)
---

# Load the workspace `AGENTS.md` into Claude via a `CLAUDE.md` `@AGENTS.md` import

_Design doc. Drafted 2026-06-08 as a `SessionStart`-hook design; revised
2026-06-09 after review found the hook approach hits Claude's 10k hook-output
cap. Status: implemented 2026-06-09 — supersedes the hook approach (recorded
below). `GEMINI.md` is deferred (open question 2)._

Guarantee that a Claude session opened in a generated workspace has the
workspace's full `AGENTS.md` (source order, edit/reference roles, the
efforts/sessions model, the filename convention) in context — without the user
prompting and without relying on Claude *choosing* to read the file. Today the
generated `CLAUDE.md` is only a prose pointer (`WORKSPACE_POINTER_MD`,
`cli.py:782`), and Claude Code does **not** read `AGENTS.md` natively.

This follows the project split — *deterministic in the CLI, judgment in the AI*:
the CLI wires the file into context mechanically; no model choice decides
whether the conventions are present.

## Verified mechanics (Claude docs, fetched 2026-06-09)

- **Claude Code reads `CLAUDE.md`, not `AGENTS.md`** (`memory.md:125`). The
  documented bridge is a `CLAUDE.md` that imports it via `@AGENTS.md`
  (`memory.md:123-143`).
- **`@path` imports are expanded and loaded into context at launch**, recursive
  to a maximum depth of four hops (`memory.md:95-97`).
- **`CLAUDE.md` files and their imports load in full regardless of length** —
  the 10k cap below does **not** apply to them (`memory.md:376`).
- For contrast, **hook output is capped at 10,000 characters** —
  `additionalContext`, `systemMessage`, and plain stdout alike; oversize output
  is spilled to a file and replaced with a preview + path (`hooks.md:704`). And
  `SessionStart` plain stdout *does* reach Claude (`hooks.md:620,919`),
  correcting an earlier draft of this doc that claimed it did not.

## Rejected: a `SessionStart` hook injecting the file

The first draft proposed a `zentaizo agents-context` subcommand emitting the
file as `SessionStart` `additionalContext`, installed through the same managed-
hook machinery as the session-title hook (`_render_claude_session_title_settings`,
`cli.py:667`). Review (Codex, 2026-06-09) killed it on the cap:
`workspace_agents("example")` is **13,620 chars** (13,753 with a framing prefix),
over the 10k limit — so the full rules would be truncated to a preview,
defeating the guarantee. Salvage options (maintain a `<=10k` "essentials"
subset, or chunk across several `additionalContext` values) add a
maintenance/drift burden for no benefit over the import below.

## Chosen: generated `CLAUDE.md` = `@AGENTS.md`

Change the generated workspace `CLAUDE.md` from the prose pointer to an import:

```
@AGENTS.md
```

This loads the full `AGENTS.md` at session start — no cap, no hook, no
subcommand, no `settings.json` merge — and it is the officially documented
pattern for a repo that keeps its instructions in `AGENTS.md`. It coexists
trivially with the session-title hook and `zentaizo sandbox --target claude`
(both write `.claude/settings.json`; this writes `CLAUDE.md`).

## Implementation (done 2026-06-09)

- `cli.py`: added `CLAUDE_IMPORT_MD = "@AGENTS.md\n"`; `create_workspace` now
  writes `CLAUDE.md` from it (`cli.py:782`). `GEMINI.md` still uses
  `WORKSPACE_POINTER_MD` pending open question 2.
- No new subcommand and no change to the managed-hook machinery; the
  session-title hook is untouched.
- `tests/test_cli.py`: the create test now asserts `CLAUDE.md` is exactly
  `@AGENTS.md` and keeps the prose-pointer assertions for `GEMINI.md`. Full
  suite green (169 tests, ruff clean).
- Docs updated: `README.md` Mechanisms bullet, `docs/workspace-format.md`
  (host-tool wiring note), and `upgrade-zentaizo.md` (existing workspaces migrate
  their `CLAUDE.md` to the import). No remaining doc follow-up.

## Tool-repo parallel (done 2026-06-09)

This repo previously used a `SessionStart` hook (`.claude/settings.json` +
`.claude/hooks/inject-agents-md.py`) to inject its own `AGENTS.md`. Retired:
this repo's `CLAUDE.md` is now `@AGENTS.md`, and the hook + script were removed.
`.claude/settings.local.json` (permissions) is untouched.

## Open questions

1. ~~**Tool repo: retire the hook for an `@AGENTS.md` import?**~~ Resolved
   2026-06-09: yes — done (see Tool-repo parallel above).
2. **Gemini:** does Gemini CLI honor `@AGENTS.md` imports in `GEMINI.md`? If yes,
   mirror the change; if no, keep its prose pointer. Verify before touching
   `GEMINI.md`.
3. **One-time import approval:** Claude shows an approval dialog for *external*
   imports (`memory.md:118`); a repo-relative `@AGENTS.md` should not count as
   external — confirm in practice.
4. **`AGENTS.md` size vs adherence:** the import loads all ~13.6k every session,
   and the docs note long instruction files reduce adherence (`memory.md:81,421`).
   Acceptable given the goal, but a standing argument to keep the workspace
   `AGENTS.md` tight.
