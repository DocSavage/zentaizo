# AI Coding-Harness Integration

_Distilled design doc — current architecture + rationale._

## What it is

Zentaizo produces and maintains a *workspace*, but the workspace is only useful
inside an AI coding harness. This subsystem is the glue that wires a generated
workspace into Claude Code (and, more loosely, other harnesses) so the assistant
arrives with the right context, names its session after the work, and attributes
its commits — all without the user prompting and without the model having to
choose to do the right thing.

It covers three concerns: (1) a Claude `SessionStart` hook that titles a session
after the active slice rather than the first thing typed; (2) loading the
workspace `AGENTS.md` into Claude in full via a `CLAUDE.md` `@AGENTS.md` import;
and (3) deterministic AI commit attribution, via a `commit-trailer` reader an
agent can call plus a bundled `prepare-commit-msg` hook as a backstop. Each piece
follows the project's core split — *deterministic work in the CLI, judgment in
the AI*: the CLI resolves identities, titles, and context mechanically, while the
agent supplies only the things a machine cannot (a good slice title, the commit
body it is already writing).

## Architecture

### Session titles from a per-slice `short_title`

A Claude session header shows a title; with none set, Claude falls back to a
truncated conversation message, which names the conversation, not the work. The
fix is a workspace-state-derived title.

- **The `short_title` field.** `changes/` and `debugging/` slices carry an
  agent-authored `short_title` in frontmatter — an ultra-short (≤ 30-char),
  discriminator-first description of the slice. `SHORT_TITLE_MAX = 30`
  (`src/zentaizo/cli.py:46`) is the budget, designed to the most compressed
  header surface. `zentaizo next-change`/`next-debugging` accept `--short-title`
  and reject an over-budget value (`normalize_short_title`, `cli.py:3204`);
  `validate` warns (never errors) on an open slice with an empty or overlong
  `short_title` (`cli.py:1026`–1032). The field is deliberately *not* named
  `session_title`, which is the name of Claude's own hook-input field.
- **The `zentaizo session-title` hook command** (`session_title_command`,
  `cli.py:4275`) reads `SessionStart` JSON on stdin and prints a `sessionTitle`
  decision. It emits `{}` when `source` is not `startup`/`resume` (the title is
  ignored otherwise) or when a `session_title` is already set (respecting a
  manual `--name`/`/rename`), and is wrapped best-effort so any exception emits
  `{}` and exits 0 — a hook must never break a session.
- **Title resolution** (`resolve_session_title`, `cli.py:3834`) walks a
  precedence chain, most-specific first: active slice `short_title` → active
  slice slug → current non-`main` effort label → workspace directory name.
  "Active slice" is the highest-counter *open* slice for the current effort
  across both `changes/` and `debugging/` (`find_active_slice`, `cli.py:3799`).
  `usable_short_title` (`cli.py:3214`) discards blanks and scaffold placeholders
  so a freshly created slice falls through rather than titling on `<...>`.
- **Installation.** The hook is a managed entry in `.claude/settings.json` under
  `hooks.SessionStart`, identified by its exact command string
  `zentaizo session-title` (`CLAUDE_SESSION_TITLE_COMMAND`, `cli.py:47`).
  `_render_claude_session_title_settings` (`cli.py:753`) deep-copies existing
  settings, drops any prior managed entry, re-adds one, and preserves
  user-authored hooks and all other settings — the same never-clobber contract
  as the commit hook's marker. `create_workspace` installs it best-effort
  (`cli.py:911`); `--no-claude-hooks` opts out, and `zentaizo claude-hooks`
  (`claude_hooks_command`, `cli.py:4314`) retrofits an existing workspace.
  Both gate the write on `_probe_claude_session_title_command` (`cli.py:792`),
  which resolves `zentaizo` on `PATH` and runs it once with empty stdin,
  requiring exit 0 — this rules out both *no* `zentaizo` on `PATH` and a *stale*
  one lacking the subcommand, either of which would fail at argparse, outside
  the best-effort guarantee.

Putting the logic in a Python subcommand (not a bundled shell script) is
deliberate: it is unit-testable, needs no `jq`, and upgrades with the CLI rather
than going stale as a copied script — the committed `settings.json` only ever
references the command name.

### Loading the workspace `AGENTS.md` into Claude

Claude Code reads `CLAUDE.md`, not `AGENTS.md`. To guarantee the workspace's full
conventions are in context at launch, `create_workspace` writes `CLAUDE.md` as a
single-line import — `CLAUDE_IMPORT_MD = "@AGENTS.md\n"` (`cli.py:423`), written
at `cli.py:868`. `@path` imports load in full at session start, with no length
cap. This replaced an earlier prose pointer and is the officially documented
pattern for a repo that keeps its instructions in `AGENTS.md`.

`GEMINI.md` is still written as the prose `WORKSPACE_POINTER_MD` pointer
(`cli.py:415`, `cli.py:869`) — whether Gemini CLI honors an `@AGENTS.md` import
was left unverified, so its behavior was not changed. The session-title hook and
the import coexist trivially: the hook writes `.claude/settings.json`, the import
writes `CLAUDE.md`.

### Commit attribution

One producer writes a cache; three readers consume it, so `edited_by` ledgers and
`Co-authored-by` trailers always report the same model identity.

- **Producer:** `zentaizo cache-commit-trailer` (`cache_commit_trailer`,
  `cli.py:543`). `--claude` reads the Claude Code statusline JSON on stdin (the
  only place the friendly model display name is exposed); `--codex` reads Codex
  config (`_read_codex_commit_trailer_config`, `cli.py:529`). It writes
  `{provider, model, effort, captured_at}` (`_write_trailer_cache`, `cli.py:503`)
  to `~/.cache/{provider}/commit-trailer/{session}.json` plus a `latest.json`
  fallback.
- **Reader A — the bundled hook**
  (`src/zentaizo/templates/hooks/prepare-commit-msg`) reads the cache, formats the
  trailer, and appends it to the message. It is **fail-open** (any error skips the
  trailer, never blocking a commit), **idempotent per provider** (a regex guard on
  `^Co-authored-by:\s+{provider}` suppresses duplicates on amend/rebase), and pure
  standard library. It is installed repo-locally as
  `.git/hooks/prepare-commit-msg` by `install_commit_attribution_hook`
  (`cli.py:457`) — into the workspace at `create_workspace` and into each editable
  repo on `fetch`. The installer refuses to overwrite an unrelated project hook
  (it refreshes only a hook carrying `HOOK_MARKER`, `cli.py:448`).
- **Reader B — `zentaizo edited`** stamps the `edited_by:` ledger on session files
  via `agent_editor_identity` (`cli.py:703`) → `_read_trailer_cache`
  (`cli.py:581`) + `_with_effort` (`cli.py:608`).
- **Reader C — `zentaizo commit-trailer`** (`commit_trailer`, `cli.py:655`) prints
  the resolved trailer to stdout for an agent to paste into a commit body. Provider
  detection mirrors the hook (`CLAUDECODE` → Claude, else `CODEX_THREAD_ID` →
  Codex); `--claude`/`--codex` force a provider, even from a non-AI shell or CI job
  with the right cache/config. Resolution reuses `_read_trailer_cache` plus the
  Codex config fallback (`_resolve_commit_trailer_identity`, `cli.py:629`), and the
  output is formatted by `_format_commit_trailer` (`cli.py:620`). Unlike the hook,
  it is **fail-loud**: on no provider, no cached model, or an incomplete identity it
  prints nothing to stdout, writes a one-line reason to stderr, and exits non-zero;
  it never falls back to `git config user.name`, since a human-named co-author
  trailer is meaningless.

The trailer-formatting logic is duplicated between the hook and `cli.py` on
purpose: the hook's self-containment (no `zentaizo` on `PATH`, no external
process) is a feature that lets it run in any repo where it was installed.
Drift is prevented by a format-lock test asserting the hook's output is
byte-identical to `commit-trailer`'s, rather than by sharing code. The generated
workspace `AGENTS.md` § Commits (`workspace_agents`, `cli.py:285`, text at
`cli.py:405`) tells the agent to run `commit-trailer` and paste the line, noting
the hook remains a best-effort backstop.

### Model-agnosticism boundary

`short_title` and the commit-trailer cache are tool-agnostic (plain frontmatter; a
provider-keyed cache). The Claude-specific surface is isolated: the
`hooks.SessionStart` entry and the `@AGENTS.md` `CLAUDE.md`, both under the
workspace's Claude-owned files. `AGENTS.md` and the `skills/` procedures stay
model-neutral, and `zentaizo session-title` / `commit-trailer` are themselves
generic subcommands — only the settings wiring and the `CLAUDE.md`/`GEMINI.md`
filenames name a specific harness.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Title source | Per-slice `short_title` frontmatter, agent-authored | The machine cannot judge what distinguishes a slice; the agent supplies it once, at creation. |
| Field name | `short_title`, not `session_title` | Avoids conflation with Claude's `session_title` hook-input field, and names the 30-char constraint. |
| Title budget | ≤ 30 chars, discriminator-first; soft-enforced on disk | Designed to the most compressed header; an empty value warns but never blocks `in-progress`. |
| Hook event | `SessionStart`, not `UserPromptSubmit` | The title tracks workspace state, not prompt content; `SessionStart` resolves it once, off the blocking pre-prompt path. |
| Hook logic location | Python subcommand, not a bundled shell script | Testable, no `jq`, cross-platform, and upgrades with the CLI instead of going stale. |
| Hook install gating | Probe a current `zentaizo` on `PATH` (run it, require exit 0) | `shutil.which` alone cannot detect a stale binary lacking the subcommand; a failure there is outside the best-effort guarantee. |
| Load `AGENTS.md` into Claude | `CLAUDE.md` = `@AGENTS.md` import | Loads the full file at launch with no length cap; the documented pattern. |
| Commit attribution shape | One cache producer + three readers | A single resolved `(model, effort)` source keeps `edited_by` and `Co-authored-by` consistent. |
| `commit-trailer` failure mode | Fail-loud (non-zero, stderr reason) | An agent shelling out can see and act on the failure, unlike the hook's silent skip. |
| Keep the hook self-contained | Do not refactor it to shell out to `commit-trailer` | Self-containment lets it run in any installed repo without `zentaizo` on `PATH`; a format-lock test prevents drift. |

## Considered and not taken

- **`SessionStart` hook injecting `AGENTS.md` as `additionalContext`** — rejected:
  the workspace `AGENTS.md` exceeds Claude's 10k hook-output cap, so the full rules
  would be truncated; the uncapped `@AGENTS.md` import is strictly better.
- **`UserPromptSubmit` for mid-session retitling** — deferred: it runs on the
  blocking per-prompt path for a value that rarely changes. The accepted cost is
  that a slice activated mid-session is not reflected until the next
  startup/resume; `/rename` is the immediate override.
- **Reusing the slug or plan H1 as the title** — rejected: the slug is lossy and
  the H1 often leads with a generic verb; `short_title` is purpose-built for the
  truncated header.
- **`GEMINI.md` `@AGENTS.md` import** — deferred pending confirmation that Gemini
  CLI honors the import; `GEMINI.md` stays a prose pointer.
- **Refactoring the hook into a thin wrapper over `commit-trailer`** — rejected to
  preserve the hook's no-dependency self-containment; a byte-identical format-lock
  test guards against divergence instead.
- **A `--format git-standard` trailer variant and a cache TTL / `--check` verifier
  mode** — deferred as non-goals; per-session keying with a `latest.json` fallback
  is sufficient, and a stale-but-right model beats a hard failure.

## See also

- `src/zentaizo/cli.py` — `session_title_command`, `resolve_session_title`,
  `find_active_slice`, `_render_claude_session_title_settings`,
  `_probe_claude_session_title_command`, `claude_hooks_command`,
  `create_workspace`; `cache_commit_trailer`, `commit_trailer`,
  `_resolve_commit_trailer_identity`, `_format_commit_trailer`,
  `install_commit_attribution_hook`, `agent_editor_identity`; the
  `CLAUDE_IMPORT_MD` / `WORKSPACE_POINTER_MD` constants and the `workspace_agents`
  § Commits text.
- `src/zentaizo/templates/hooks/prepare-commit-msg` — the bundled, self-contained
  attribution hook.
- `docs/cli.md` — `session-title`, `claude-hooks`, `commit-trailer`,
  `cache-commit-trailer`, `edited`, `next-change`/`next-debugging --short-title`.
- `docs/workspace-format.md` — `short_title`, the `CLAUDE.md` `@AGENTS.md` wiring,
  and the `edited_by:` ledger / commit-trailer cache.
- `README.md` — Mechanisms (model-neutral instructions; deterministic tooling).
