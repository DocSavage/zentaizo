---
created: 2026-06-15
status: planned
edited_by:
  - 2026-06-15  Claude Opus 4.8 (1M context, reasoning xhigh)
  - 2026-06-16  Codex gpt-5.5 (reasoning xhigh)
---

# A `zentaizo commit-trailer` command: a stdout reader for AI commit attribution

_Implementation plan. Promotes the brainstorm
[`2026-06-15-commit-trailer-command.md`](../brainstorming/2026-06-15-commit-trailer-command.md)
to a decided change. The brainstorm asked the right question — "the CLI already
resolves identity deterministically, so why deliver it only through a per-repo
git hook?" — and this plan answers it, corrects one inaccurate premise in the
trigger, and scopes the smallest change that closes the real gap: a third
**reader** of the existing trailer cache that prints the resolved
`Co-authored-by` line to stdout, so an agent can obtain attribution without
any per-repo install._

## The question this answers (the user's ask)

> Was there a reason we didn't just make it a tool call that returns the
> attribution string, to paste into the commit body the agent is already writing?

No blocking reason — it was an emphasis choice, and the read-side primitive
already exists. The evidence:

- The hook was introduced in `2308a4a` ("Add shared AI commit-attribution hook +
  cache-commit-trailer producer", 2026-06-02). Its stated goal was attribution
  that is **automatic and mechanical** — "records the model + reasoning effort
  behind AI commits **without relying on any machine-local helper**" — and it
  deliberately attributes commits made inside an assistant session even when
  the agent forgets to paste a trailer or a helper/tooling path creates the
  commit. That is an **enforcement backstop**, and a hook is the right shape for
  enforcement.
- A printed string was simply not built, because at the time the only other
  reader needed was for frontmatter (`zentaizo edited`), which is a CLI call,
  not a commit-time mutation.
- Crucially, the deterministic resolver the brainstorm wants to reuse **already
  exists and is already a second reader**: `_read_trailer_cache` (`cli.py:581`)
  + `_with_effort` (`cli.py:607`) back `zentaizo edited`'s `edited_by` stamping.
  Adding a third reader that prints a trailer is small and introduces **no new
  resolution logic**.

So the command is strictly additive and well-precedented. It does not replace
the hook; it covers the path the hook structurally cannot (see below).

## One correction to the brainstorm's trigger

The brainstorm says vendored editable repos "never receive" the hook. That is
**not accurate for repos fetched through `zentaizo fetch`**: `fetch_edit_repo`
installs it on first clone (`cli.py:1332`) and refreshes it on later fetches
(`cli.py:1347`). The real gaps where the hook is absent or inert are narrower
and worth stating precisely, because they are exactly what the command fixes:

1. **Sources that bypass `fetch`** — a `path:`/symlinked editable repo, or a
   repo cloned by hand into `repos/`, never runs `fetch_edit_repo`, so it is
   never reached by the installer. (This is the likely root cause of the
   `repos/kvdbclient` miss — "cloned or symlinked".)
2. **A pre-existing `prepare-commit-msg`.** The installer refuses to clobber a
   hook it didn't write (`install_commit_attribution_hook`, `cli.py:484`,
   returns `None`). Any repo with its own hook gets **no** attribution, silently.
3. **Hook-missing/shadowed commit paths** — many GUI clients, `core.hooksPath`
   shadowing, and fresh re-clones. (`prepare-commit-msg` still runs under
   `git commit --no-verify`, so that flag is not one of the gaps.)
4. **Silent fail-open.** The hook is fail-open by design (`prepare-commit-msg`
   docstring, line 18) — every absence/error degrades to "no trailer," and the
   agent cannot reliably detect this (the brainstorm's own point about
   `git rev-parse --git-path hooks` returning a cwd-relative path).

The command's value proposition, corrected: **uniform across every repo with
zero install, fully visible (one line in the body the agent already authors),
and fail-loud** — it exits non-zero with a clear message when attribution can't
be resolved, the opposite of the hook's silent no-op.

## Current architecture (one producer, two readers, a duplicated formatter)

- **Producer:** `cache_commit_trailer` (`cli.py:543`) — `--claude` reads the
  statusline JSON on stdin; `--codex` reads Codex config
  (`_read_codex_commit_trailer_config`, `cli.py:529`). Writes
  `{provider, model, effort, captured_at}` via `_write_trailer_cache`
  (`cli.py:503`) to `~/.cache/{provider}/commit-trailer/{session}.json` and
  `latest.json`.
- **Reader A — commits:** the `prepare-commit-msg` hook template
  (`src/zentaizo/templates/hooks/prepare-commit-msg`) reads the cache
  (`_read_cache`, line 38), formats the trailer (`_claude_trailer`/
  `_codex_trailer`, lines 56–78), and is idempotent per provider (line 120).
- **Reader B — frontmatter:** `zentaizo edited` via `agent_editor_identity`
  (`cli.py:639`) → `_claude_editor_identity`/`_codex_editor_identity` →
  `_read_trailer_cache` + `_with_effort`.

The trailer-formatting logic is **duplicated** between the hook (lines 56–78)
and `cli.py` (`_with_effort`, line 607). The hook docstring (cli.py:586) records
*why*: the hook "must stay self-contained, so the two cannot share code." That
constraint is load-bearing — see the decision on the hook below.

## Proposal: `zentaizo commit-trailer`

A third reader that **prints** the resolved trailer to stdout and **fails loudly**
when it cannot.

```
zentaizo commit-trailer [--claude | --codex]
```

Behavior:

- **Provider detection** mirrors the hook's `_provider_trailer` (line 81):
  `CLAUDECODE` env → Claude; else `CODEX_THREAD_ID` → Codex. `--claude`/`--codex`
  force a provider, including from a non-AI shell/CI job that has the right
  cache or Codex config available (not mutually-required like the producer —
  detection is the default; the flags are overrides).
- **Resolution reuses existing helpers** — `_read_trailer_cache` +
  `_with_effort`, plus the Codex cold-start config fallback already in
  `_codex_editor_identity` (`cli.py:628`). No new resolution logic.
- **Success:** print exactly one line to stdout and exit `0`:
  - Claude: `Co-authored-by: Claude {model+effort} <noreply@anthropic.com>`
  - Codex:  `Co-authored-by: Codex {model} (reasoning {effort}) <noreply@openai.com>`
  These must be **byte-identical** to what the hook emits for the same cache.
  Provider validity matches the hook: Claude needs a model (effort is optional,
  with `CLAUDE_EFFORT` as fallback); Codex needs both model and effort.
- **Fail-loud:** if provider detection fails, no model can be resolved, or the
  resolved provider identity is incomplete, print nothing to stdout, write a
  one-line reason to **stderr**, and exit non-zero — e.g.
  `commit-trailer: no cached model identity (run inside a Claude/Codex session, or 'cache-commit-trailer' first)`.
  This is the deliberate improvement over the hook's silent skip: an agent that
  shells out sees the failure and can act, rather than committing unattributed.
- **Human shell with no provider override:** no AI provider detected → exit
  non-zero with a message that a `Co-authored-by` line is for AI co-authorship
  (unlike `edited`, which stamps the human as editor, a trailer naming the human
  as co-author is meaningless). `commit-trailer` does **not** fall back to
  `git config user.name`.

### Why this is a clean fit

The trailer is just `agent_editor_identity()` wrapped with a provider email.
`agent_editor_identity()` already returns `Claude Opus 4.8 (1M context, reasoning
xhigh)` / `Codex <model> (reasoning <effort>)`. The only behavioral difference:
that function returns a `"<Provider> (model unknown)"` placeholder when the
session is AI but the cache is cold, whereas `commit-trailer` must **fail** in
that case (a placeholder trailer is worse than a loud error). So the command
resolves `(model, effort)` directly and applies the provider-specific validity
rules above, rather than reusing the placeholder-returning wrapper verbatim.

## Decision: keep the hook self-contained — do **not** refactor it to a thin wrapper

The brainstorm's step 2 proposes rewriting the hook to shell out to
`zentaizo commit-trailer`, eliminating the duplicated formatter. **Recommend
against**, for a concrete reason the brainstorm didn't weigh:

- The hook's self-containment (pure stdlib, no external process) is a **feature**,
  not incidental. It runs at commit time in *any* repo where it was installed —
  including vendored editable repos whose commit environment may not have
  `zentaizo` on `PATH`. Shelling out makes the hook depend on `zentaizo` being
  importable/on-PATH in every such repo, and complicates fail-open (a missing
  binary must still degrade cleanly). That trades a hard guarantee for ~15 lines
  of saved duplication.

Instead, kill the **drift risk** without sharing code:

- Add a test that builds a known cache and asserts the hook's emitted trailer is
  **byte-identical** to `zentaizo commit-trailer`'s stdout, for both providers.
  The two implementations stay independent (as the cli.py:586 docstring
  requires) but can never silently diverge.

(If we later decide the duplication is genuinely costly, an optional shell-out
*with inline fallback* could be revisited — but it is out of scope here.)

## Canonical trailer format

Two forms exist in the wild (brainstorm §"Trailer-format reconciliation"): the
canonical lowercase, reasoning-folded form the hook and `edited` already emit,
and a hand-written `Co-Authored-By: … (no reasoning)` variant. **Standardize on
the existing canonical form** — `commit-trailer` emits it, the workspace guidance
tells agents to use the command instead of hand-writing, and the drift
disappears at the source. A `--format git-standard` (capitalized, reasoning-free)
is a **non-goal** for this change; add it only if a downstream repo asks.

## Guidance / discoverability

The surest way an agent calls the command is the generated guidance, not
`docs/cli.md` alone. Update, in order of impact:

1. **`workspace_agents()` § Commits** (`cli.py:401`–405): tell the agent to run
   `zentaizo commit-trailer` and paste the line into the body it is already
   writing; note it needs no per-repo hook and works in vendored repos. Keep it
   lean (defer mechanics to the command) per the repo's generated-instructions
   rule.
2. **`docs/cli.md`:** add a `commit-trailer` entry beside `cache-commit-trailer`
   and `edited`; cross-link the three readers and one producer.
3. **Closeout/handoff guidance:** the commit step in
   `templates/skills/plan-and-implement.md` (§ Closing out) — point at the
   command where commit attribution is described.

## Tests (`tests/test_cli.py`)

1. Fresh per-session cache → stdout is the exact canonical line; exit 0 (Claude
   and Codex).
2. `latest.json`-only (no per-session key) → resolves via fallback; exit 0.
3. Missing/empty cache → no stdout, non-zero, reason on stderr.
4. Incomplete Codex identity (model without effort, or effort without model) →
   no stdout, non-zero, reason on stderr.
5. Human shell (no `CLAUDECODE`/`CODEX_THREAD_ID`, no provider override) →
   non-zero, no trailer.
6. `--claude`/`--codex` override env detection and may run outside an AI env
   when the provider's cache/config is available.
7. **Format-lock:** hook output == `commit-trailer` stdout for an identical
   cache (both providers).
8. **Idempotency-with-hook:** agent pastes the canonical line into the body and
   the hook also runs → its `^Co-authored-by:\s+{provider}` guard (hook line 120)
   suppresses the duplicate (no double trailer).

## Implementation steps

1. `cli.py`: add `_format_commit_trailer(provider, model, effort) -> str` (pure;
   Claude/Codex email map) and `commit_trailer(args)`. Resolve via
   `_read_trailer_cache` (+ Codex config fallback), detect provider from env with
   `--claude`/`--codex` overrides, print-or-fail-loud as specified.
2. Register the subparser next to `cache-commit-trailer` (`cli.py:4526`);
   `set_defaults(func=commit_trailer)`. Optional `--claude/--codex` (a
   *non-required* mutually-exclusive group, unlike the producer's required one).
3. Update `workspace_agents()` § Commits, `docs/cli.md`, and the
   `plan-and-implement.md` closeout note.
4. Add the eight tests above.
5. `pixi run check` (ruff + tests).

## Decisions needed

- **Staleness / TTL.** The cache already stamps `captured_at` (`cli.py:512`) but
  no reader checks it. MVP recommendation: rely on per-session keying and the
  `latest.json` fallback (no TTL) — sessions are long-lived and a stale-but-right
  model is better than a hard failure. Option if we want strictness: warn (or
  fail) when only `latest.json` matched and `captured_at` is older than a
  threshold. **Recommend: no TTL in v1.**
- **`--check <msgfile>` mode.** A verifier (`commit-trailer --check`) could back a
  `commit-msg` enforcement hook and a CI lint. **Recommend: defer** — separate
  follow-up; the printer is the immediate need.

## Non-goals

- Removing or demoting the hook (it remains the enforcement backstop for commits
  created inside an assistant session when the agent or helper path did not
  paste the trailer).
- A `--format git-standard` variant.
- Changing the producer (`cache-commit-trailer`) or the cache schema.
