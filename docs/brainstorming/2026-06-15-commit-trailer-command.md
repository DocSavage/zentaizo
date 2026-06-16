---
created: 2026-06-15
status: brainstorming
edited_by:
  - 2026-06-15  Claude Opus 4.8 (1M context, reasoning xhigh)
---

# A `commit-trailer` command: make attribution a deterministic primitive, demote the hook to an optional client

_Brainstorm / idea backlog — hypothesis, not a commitment. Captured during a
zen-ACG session (2026-06-14/15) where a commit in the vendored editable repo
`repos/kvdbclient` landed **unattributed**: the `prepare-commit-msg` hook is
installed only in the workspace repo, not in vendored editable repos, so nothing
stamped the trailer. That surfaced a design question — given the tool already
resolves identity deterministically in the CLI, why deliver it through a
per-repo git hook at all, rather than a command the agent calls and pastes (it
is writing the commit body anyway)? This aligns with the tool's stated principle,
"deterministic in the CLI, judgment in the AI."_

## The trigger

- A fork commit landed with no `Co-authored-by` trailer. Root cause: git hooks
  are per-repository (`.git/hooks/`), not shared; `core.hooksPath` is unset. The
  hook lives in the **workspace** repo only — vendored editable repos (cloned or
  symlinked into `repos/`) never receive it.
- An agent trying to detect "is the hook present?" is itself error-prone
  (`git rev-parse --git-path hooks` returns a *relative* `.git/hooks`, easy to
  resolve against the wrong cwd). So "let the hook handle it" silently degrades
  to "no attribution," and the agent can't reliably tell.

## Current architecture (recap, with pointers)

The identity resolution is **already centralized and deterministic** — the model
does not name itself; the harness feeds it in:

- **Producer:** `zentaizo cache-commit-trailer` (`cli.py:543`) — `--claude`
  reads the Claude Code statusline JSON on stdin; `--codex` reads Codex config
  (`_read_codex_commit_trailer_config`, `cli.py:529`). It writes `(model,
  effort)` via `_write_trailer_cache` (`cli.py:503`) to
  `~/.cache/{provider}/commit-trailer/{key}.json` plus `latest.json`, keyed by
  session id (Claude) / `CODEX_THREAD_ID` (Codex).
- **Reader A (commits):** the `prepare-commit-msg` hook template
  (`src/zentaizo/templates/hooks/prepare-commit-msg`) reads that cache (:40),
  formats the trailer (:64–78), and skips if one is already present (:120).
- **Reader B (frontmatter):** `zentaizo edited` reads the same cache
  (`_read_trailer_cache`, `cli.py:581`; effort folded into the model parens by
  `_fold_effort_into_model`, `cli.py:608`) to stamp `edited_by`.

So the cache has **one producer and two readers** — and the trailer-formatting
logic is **duplicated** between the hook template (:64–78) and `cli.py`.

## The gap

There is no **stdout "printer"** reader — the consumer the agent-paste path
needs. The only commit-time delivery is the hook, which carries two costs:

1. **Per-repo install.** Exactly the gap that bit the fork. Vendored editable
   repos don't get it; a re-clone wipes it; a GUI or `--no-verify` skips it.
2. **Safe-interception complexity.** Most of the hook is handling `-m`/`-F`/
   editor/amend/merge paths and idempotency (:120) — necessary only because it
   mutates the message mid-commit. The agent-paste path sidesteps all of it: the
   agent includes one line in the body it already authors.

## Proposal

Add **`zentaizo commit-trailer`** — a third reader that **prints** the resolved
trailer to stdout and **fails loudly** (non-zero + clear stderr) when the cache
is missing or stale, so an agent notices instead of silently committing
unattributed (strictly better than the hook's silent no-op).

- It reuses `_read_trailer_cache` + `_fold_effort_into_model` (no new resolution
  logic).
- Documented workflow (`AGENTS.md` "Commits", handoff "Recording" template):
  call it, paste the line. Works in the workspace **and every vendored repo**
  with zero install — the fork problem disappears.
- **Demote the hook to an optional thin client:** rewrite the template so it
  shells out to `zentaizo commit-trailer` instead of re-implementing the format
  (:64–78) and cache read (:40). Repos/humans wanting mechanical enforcement
  install it; everyone else uses the command. One resolver, thin clients, no
  duplication.

## Why command-as-primitive beats hook-as-primitive (for this workflow)

- **Uniform across repos**, no per-repo install (the concrete win).
- **The agent already composes the body** — one extra line, fully visible, no
  mid-commit magic.
- **No hook fragility** — `--no-verify`, GUIs that skip hooks, re-clone,
  `core.hooksPath` shadowing.
- The hook's *only* unique value is attributing commits the agent didn't author
  (human commits, other tools, a forgetful agent). That's an enforcement
  backstop — worth keeping as an option, not as the primary mechanism.

## Shared dependency and a real failure mode

Both paths depend on the cache being populated by the harness. If
`cache-commit-trailer` didn't run (headless/cron, or a session type the
statusline hook doesn't cover) or the entry is stale, **both produce nothing**.
The command should make this explicit:

- Define staleness (cache currently keyed by session id with a `latest.json`
  fallback, no TTL — `_write_trailer_cache`, `cli.py:503`). Options: error if no
  per-session entry and `--allow-latest` not passed; or stamp the cache with a
  timestamp and warn past a threshold.
- Decide human-shell behavior: fall back to `git config user.name` (as `edited`
  does) or print nothing and exit non-zero.

## Trailer-format reconciliation (decide canonical)

Two forms exist in the wild, and they diverge:

- Canonical (hook + `edited`): `Co-authored-by: Claude {model} (… reasoning
  {effort}) <noreply@anthropic.com>` — lowercase, reasoning folded in
  (e.g. `Co-authored-by: Claude Opus 4.8 (1M context, reasoning xhigh) …`).
- A hand-written variant seen in the kvdbclient fork: `Co-Authored-By: Claude
  Opus 4.8 (1M context) <noreply@anthropic.com>` — capital-A, no reasoning.

`commit-trailer` should emit the **canonical** form so hand-authored drift
disappears. (Open: do we want a `--format git-standard` for repos that prefer
the capitalized, reasoning-free style?)

## Open questions

- **Idempotency when both are active:** if an agent pastes *and* a thin-wrapper
  hook is installed, the hook's existing `^Co-authored-by:` guard (:120) must
  still suppress a duplicate — verify after refactor.
- **`--check` mode?** A `commit-trailer --check <msgfile>` that verifies a
  trailer is present could back a `commit-msg` (not `prepare-`) enforcement hook
  and a CI lint.
- **Provider selection:** the command should auto-detect provider from which
  cache entry is fresh (Claude vs Codex), mirroring the hook, or take
  `--claude/--codex` like the producer.
- **Discoverability:** the surest way an agent actually calls it is the
  generated workspace `AGENTS.md` text (`workspace_agents()`) plus the handoff
  "Recording" template — update both, not just `docs/cli.md`.

## Candidate next steps

1. Add `commit-trailer` to `cli.py` reusing `_read_trailer_cache` +
   `_fold_effort_into_model`; print to stdout, fail-loud on missing/stale.
2. Refactor `src/zentaizo/templates/hooks/prepare-commit-msg` to a thin wrapper
   calling the command (drop the duplicated formatter at :64–78 and cache read
   at :40); keep it optional, preserve the idempotency guard.
3. Update guidance: `workspace_agents()` "Commits", `docs/cli.md`, and the
   handoff "Recording" template — call `zentaizo commit-trailer`, paste the line;
   note it works without a per-repo hook.
4. Decide canonical trailer format (and whether to offer `--format`).
5. Tests under `tests/` for: fresh cache → correct line; stale/missing → non-zero;
   human fallback; idempotency with the thin-wrapper hook.

_Not tracked by an effort yet; this is a docs-only drop to pick up later. If
implemented, it's editable-repo work in `repos/zentaizo` (→ `~/work/zentaizo`)
and would land on that repo's git history, separate from zen-ACG workspace
notes._
