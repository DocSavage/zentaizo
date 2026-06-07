# Session titles from a per-slice `short_title`: a Claude `SessionStart` hook

_Design doc. Drafted 2026-06-07. Status: proposed (not yet implemented)._

Give a Claude Code **Remote Control** session a title that names *the work*, not the
first thing the user happened to type. The title is driven by a short, front-loaded
**`short_title`** the planning agent writes when it creates a `sessions/changes/` slice —
so the title sharpens from the workspace name to the effort to the specific slice as work
progresses, and the most distinguishing words survive the header's truncation.

This splits cleanly along the project's core principle — *deterministic in the CLI,
judgment in the AI*: the CLI installs the hook and resolves the title mechanically; an
agent supplies the one thing a machine cannot — a good short description of the slice.

## Problem

Claude Code's Remote Control header shows a session **title** (bold) over the working
directory (subtitle). With no explicit title, the title falls back — per Claude Code's
documented resolution order — to *a meaningful message from the conversation*, truncated.
A user opening Remote Control for the first time in the `zen-ACG` workspace saw:

> **configure remote session namin…**
> zen-ACG

That title is an artifact of the conversation, not the work. It is unstable (it tracks
whatever the user last asked), uninformative across sessions (every slice of an effort
looks alike), and the truncation amputates the end of a sentence rather than preserving a
discriminator. We want the title to answer, at a glance from a phone: *which workspace,
which effort, which slice* — with the **most distinguishing attribute first**, because
the header truncates aggressively (the example above cut off at ~30 characters, and the
iPhone header is the most compressed target).

There is no Claude Code **setting** that changes the fallback away from "last meaningful
message." The only documented levers are `--name`/`/rename` (manual) and a `SessionStart`
hook that emits a `sessionTitle` (automatic). So the automatic path is a hook — and the
question becomes *what should the hook name the session*.

### What Claude Code gives us (verified against the docs)

From `code.claude.com/docs/en/hooks.md`, the `SessionStart` hook:

- May return `{"hookSpecificOutput": {"hookEventName": "SessionStart", "sessionTitle": "…"}}`.
  Per the docs, `sessionTitle` "Sets the session title, with the same effect as
  `/rename`… Applies only when `source` is `startup` or `resume`; ignored on `clear` and
  `compact`."
- Receives on stdin a `source` field (`startup` | `resume` | `clear` | `compact`) and an
  optional `session_title` carrying the *already-set* title (e.g. from `--name` or a prior
  `/rename`), so a hook "can check `session_title` first to avoid overwriting a title the
  user set explicitly."

This is everything the design needs: a place to compute a title, a signal for *when* it
applies, and a way to be a good citizen about a title the user set by hand.

## The two pieces

1. **`short_title`** — a new, agent-authored frontmatter field on `sessions/changes/` and
   `sessions/debugging/` plans: an ultra-short (≤ 30-character), front-loaded description
   of the slice. This is the *judgment* half, and it is **tool-agnostic** — just
   frontmatter any agent writes and any tool could read.
2. **`zentaizo session-title`** — a Claude `SessionStart` hook handler that reads the
   workspace's current task and emits the `sessionTitle`. This is the *deterministic* half,
   and it is the only Claude-specific surface (it lives entirely under `.claude/`).

### Why `short_title` and not `session_title`

The field is deliberately **not** named `session_title`, even though it feeds the session
title. Claude Code's `SessionStart` hook *input* already carries a stdin field named
`session_title` (the already-set title), which the hook reads to avoid clobbering a manual
`/rename`. A frontmatter field of the same name would read as the same thing in two
places that are in fact different sources (plan frontmatter vs hook stdin). `short_title`
sidesteps that conflation and, as a bonus, names the field's defining constraint: it is
*short* (≤ 30 chars), which is the whole point.

### Piece 1 — the `short_title` field

Today the CLI fills the deterministic frontmatter (`status`/`created`/`label`,
first `edited_by:`) and the agent fills `editable_repos` and the body
(`skills/plan-and-implement.md` § Drafting the plan, step 2). `short_title` joins the
agent-filled set, authored at the moment the slice is created — when the planning agent
has the sharpest sense of what makes this slice distinct from its siblings.

It is **not** the body's `# <Concise plan title>` H1 and **not** the filename `slug`:

| Token | Audience | Shape | Example |
|---|---|---|---|
| `slug` (filename) | the filesystem / `path slice` | kebab, terse, stable | `dvid-reader` |
| H1 plan title | a human reading the plan | a readable sentence-ish title | `DVID → ACG supervoxel ingest reader` |
| `short_title` (new) | a phone-sized truncated header | ≤ 30 chars, discriminator first | `DVID supervoxel reader` |

**Why a dedicated field and not reuse the slug or H1.** The slug is normalized for
filenames (terse, lossy); the H1 is a comfortable title that often *leads with a generic
verb* ("Implement the…", "Add…") — exactly the words truncation should never spend its
first 30 characters on. The hook needs a machine-readable value it can read without
parsing markdown, and the field's whole reason to exist is to be optimized for the
truncated header. Keeping it separate also lets `effort show` / `path active` print it.
The body H1 stays the plan's own readable title, authored independently (decided: keep
both — see Decisions).

**`short_title` style rules** (these ship in the template guidance and in
`plan-and-implement.md`):

- **Lead with the most distinguishing attribute** — the subsystem, object, or specific
  verb that separates this slice from its sibling slices in the same effort. Not the
  effort name (already context), not a generic scaffolding verb.
- **≤ 30 characters — a hard budget, not a soft target.** The iPhone Remote Control header
  is the most compressed surface; design to it. The discriminator must land within the
  first ~30 chars (so even a slightly longer value degrades gracefully).
- **Noun phrase or imperative**, sentence case, no trailing period, no `label`/effort prefix.
- **Disambiguates within the effort.** A reader scanning an effort's slices should tell
  them apart by `short_title` alone.

Examples (effort `ingest`), each ≤ 30 chars:

| Weak (generic-first) | Strong (discriminator-first) |
|---|---|
| `Implement the reader for DVID volumes` | `DVID supervoxel reader` (22) |
| `Add Arrow-native edge storage` | `Arrow edge store, not protobuf` (30) |
| `Update traversal to support time travel` | `Timestamped-root traversal` (26) |

**How it is authored** — two complementary entry paths, mirroring the existing
CLI-fills-mechanics / agent-fills-judgment split:

- `zentaizo next-change <slug> --short-title "…"` — optional flag. When given, the CLI
  writes it into frontmatter atomically at creation and validates the 30-char budget
  (warns, or refuses, past the cap). This is the preferred one-step path.
- When the flag is omitted, the scaffold leaves a `short_title:` placeholder, and
  `plan-and-implement.md` instructs the agent to fill it before moving the slice to
  `in-progress`. Enforcement is **soft**: an empty `short_title` does not block the status
  transition; it surfaces as a `validate`/lint nudge, and the hook degrades gracefully via
  the resolution chain below.

The frontmatter contract in `plan-template.md` gains one line; the
CLI-consumed-contract comment is extended to list `short_title` among the fields
`next-change`/`next-debugging` may string-replace.

### Piece 2 — the `zentaizo session-title` hook handler

A new subcommand reads the hook JSON on stdin and prints the `SessionStart` decision
JSON. Pseudocode:

```
read stdin as JSON (lenient: empty/garbage -> {} -> fall through to dir name)
source = input.get("source")
if source not in {"startup", "resume"}: emit {} ; exit 0   # title ignored anyway
if input.get("session_title"):        emit {} ; exit 0   # respect --name / /rename
title = resolve_title(cwd)
emit {"hookSpecificOutput": {"hookEventName": "SessionStart", "sessionTitle": title}}
```

(Note the only place the string `session_title` appears in the hook is the *stdin input*
check above — the frontmatter field it reads is `short_title`, the deliberate distinction
from § "Why `short_title`".)

`resolve_title()` reuses helpers that already exist in `cli.py` — no new building blocks:

1. **active slice `short_title`** — `find_active_plan(ws, current_label)` →
   `read_frontmatter(path)["short_title"]`, if present and not the empty placeholder.
2. else **active slice `slug`** — recovered from the active plan's filename.
3. else **current effort label** if it is not the reserved `main` — `load_efforts(ws)["current"]`.
4. else **workspace directory basename** (`ws.name`) — the brand-new-workspace / `main`-effort
   case. (Retained deliberately: a bare directory-name title is liked when there is no
   specific task — see Decisions.)

The whole subcommand is wrapped best-effort: any exception → emit `{}` and exit 0. A hook
must never break a session, and an empty object is a valid "no opinion" response. This
matches `install_commit_attribution_hook`'s "never raise" posture.

The resolution chain is exactly the user's stated preference — *the Zentaizo task it's
running, or the directory name* — refined into a precise precedence: the more specific
the live work, the more specific the title.

## Installation

Claude `SessionStart` hooks are configured in `.claude/settings.json` under `hooks`, not
in `.git/hooks`. The project already has the merge machinery for that file
(`_render_claude_settings` deep-copies existing settings and swaps only a *managed*
block, preserving the user's rules). We follow the same pattern for a managed
`hooks.SessionStart` entry:

```jsonc
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "zentaizo session-title" } ] }
    ]
  }
}
```

- The managed entry is identified by its command (`zentaizo session-title`), so a
  re-render drops the old managed entry and re-adds it (stable, idempotent) while leaving
  any user-authored `SessionStart` hooks and all other events untouched — the same
  never-clobber contract as the commit-attribution hook's `HOOK_MARKER`.
- **At create time:** `create_workspace` writes the managed hook into
  `.claude/settings.json` (best-effort, never fails creation), with a `--no-claude-hooks`
  opt-out paralleling `--no-commit-hook`. This is the "installed when a new workspace is
  created" requirement.
- **For existing workspaces:** a small `zentaizo claude-hooks` subcommand runs the same
  merge so workspaces created before this change (e.g. `zen-ACG`) can adopt it, and a line
  in `upgrade-zentaizo.md` points there.

**Putting hook logic in a Python subcommand, not a bundled shell script,** is deliberate:
it is unit-testable, needs no `jq`, works cross-platform, and — crucially — *upgrades with
the CLI* instead of going stale as a copied script (the very rot the
`upgrade-zentaizo` procedure exists to fix). The scaffolded `settings.json` only ever
references the command name.

## Known limitation: the title is set at session start, not on slice switch

`sessionTitle` only applies on `startup` and `resume` (ignored on `clear`/`compact`), and
there is no documented CLI path to retitle a *live* session (only the interactive
`/rename`). So a slice created or activated **mid-session** is not reflected until the
next resume; the immediate override is `/rename`.

This is acceptable because it aligns with the dominant workflow. In the planner/implementor
split (`plan-and-implement.md` § Handing off), the implementing session *starts* (or
resumes) with the slice already created — so `SessionStart`-time resolution picks up the
right `short_title` exactly when an implementing session begins. We document the
limitation rather than engineer around it.

## Secondary benefit: the `short_title` is reusable

Once slices carry a `short_title`, the CLI's own listings get more legible at no extra
cost: `zentaizo effort show` and `zentaizo path active` can print it next to each slice's
id/slug, so a maintainer scanning an effort reads intent, not filenames. Optional, but it
raises the field's payoff beyond the Claude-only hook.

## Model-agnosticism boundary

- `short_title` is plain frontmatter: tool-agnostic, authored by whatever agent runs
  `next-change`, readable by any future consumer. It belongs in the generic
  `plan-template.md` / `plan-and-implement.md`.
- The `SessionStart` hook + `.claude/settings.json` entry are Claude-Code-specific and
  stay isolated under `.claude/`. `AGENTS.md` stays model-agnostic; no other tool is
  affected. (`zentaizo session-title` is a generic subcommand; only the settings wiring
  names Claude.)

## Decisions (resolved 2026-06-07)

1. **Field name → `short_title`.** "session" was wanted in the name, but `session_title`
   collides with Claude's hook-input field; `short_title` avoids the conflation and names
   the 30-char constraint.
2. **Truncation budget → 30 characters**, designed to the iPhone header (the most
   compressed surface), discriminator-first.
3. **Soft enforcement.** An empty `short_title` nudges (lint/`validate`) but does not block
   `in-progress`; the hook falls back through the resolution chain.
4. **Keep the body H1 separate** — authored independently, not derived from `short_title` —
   and **retain the directory-name fallback** (resolution step 4): a bare workspace-name
   title is desirable when there is no specific task.

## Open questions

1. **Retrofit ergonomics.** Standalone `zentaizo claude-hooks`, or fold the
   create-time-and-retrofit install behind one verb shared with `create`?
2. **Listings.** Ship the `effort show` / `path active` `short_title` display in the same
   change, or defer it as a follow-up?

## Implementation sketch (for the follow-on `sessions/changes/`-style slices)

1. **`short_title` field** — add to `plan-template.md` frontmatter + the contract comment;
   extend `scaffold_plan()` and `next-change`/`next-debugging` to accept `--short-title`
   and string-replace it (with the 30-char check); add the authoring step + style rules to
   `plan-and-implement.md`.
2. **`zentaizo session-title`** — new subcommand + `resolve_title()` reusing
   `find_active_plan` / `read_frontmatter` / `load_efforts`; best-effort wrapper.
3. **Settings install** — managed `hooks.SessionStart` merge (mirror
   `_render_claude_settings`); call from `create_workspace` (+ `--no-claude-hooks`); add
   `zentaizo claude-hooks` for retrofit; note it in `upgrade-zentaizo.md`.
4. **Listings (optional)** — show `short_title` in `effort show` / `path active`.
5. **Tests** (`tests/test_cli.py`) — title precedence chain; `session_title` (stdin)
   respected; `source` filtering (clear/compact → `{}`); empty/garbage stdin → `{}`;
   settings merge idempotency and user-hook preservation; `--short-title` scaffolding +
   30-char handling.
6. **Docs** — `docs/cli.md` (new subcommands), `docs/workspace-format.md` (the field),
   README workspace layout if it enumerates frontmatter.
