---
created: 2026-06-10
status: brainstorming
edited_by:
  - 2026-06-10  Claude Fable 5 (1M context, reasoning xhigh)
---

# Branching across efforts: trunk-first defaults, per-repo granularity, and the concurrency boundary

_Brainstorm / idea backlog — hypotheses, not commitments. Captures a design
discussion (2026-06-09/10) that started from a Codex review of how
`effort set-branch` reads to a new user (which drove the README workflow
restructure, commit `6b39472`) and turned into: when do effort branches merge
back, and is isolating efforts on branches a cost worth paying?_

## The model as it stands (recap)

- Efforts are decoupled from branches. The effort label names the work; the
  registry (`sessions/efforts.json`) records, per editable repo, a
  `{branch, base}` pair via `zentaizo effort set-branch` — bare `--repo NAME`
  attaches a repo with `branch: null` ("touched, no branch yet"),
  `--repo NAME=BRANCH` records a real branch.
- `base` is the merge-base of the recorded branch against the repo's pinned
  atlas `ref`, falling back to `origin/<ref>` (`compute_base`, `cli.py:2967`).
- The atlas `ref` stays pinned to the durable default (usually `main`); the
  lock records what was fetched. Summaries are generated from the locked
  state (`summarize_workspace`), i.e. they describe trunk, not branches.
- Each `repos/<name>` is its own contained git clone with one working tree.
- The reserved `main` effort is the deliverable trunk: work flows there until
  it warrants a separate effort.

## When does an effort's branch merge back?

**Hypothesis: merge per slice, not per effort.** An effort is a planning unit
that can outlive many landings. Slices carry acceptance criteria and an
`## Outcome`; a slice that passes its checkboxes is landable on its own.
Holding all branches open until the effort closes recreates the long-lived
feature branch, multiplied by N repos. The rhythm that fits the existing
pieces: branch → land one slice (or a small coherent group) through the
repo's normal PR/CI process → record the landing in the slice's Outcome →
branch again if the next slice needs it. `zentaizo effort close` is the
registry-level bookend after every branch has merged or been deliberately
abandoned.

**Cross-repo contract changes need an explicit landing order**, owned by the
effort doc: separate repos cannot land atomically, so sequence
backward-compatibly — provider lands with the old contract still supported,
then consumers, then the compat shim is removed.

**Gap noticed:** the registry records `branch` and `base` but has no
*disposition* — nothing distinguishes "branch open", "merged at sha X", and
"abandoned". Today that history lives only in plan Outcomes. If it becomes
painful, the small fix is `effort close` (or `set-branch --merged <sha>`)
recording how each repo's branch landed.

## What does branch isolation cost the other efforts?

Three escalating costs; the third is the structural one:

1. **Diff-level blindness, partially mitigated.** Effort B plans against a
   world effort A is about to change. Zentaizo blunts this better than plain
   git: the registry and effort docs are visible to every session, so other
   efforts see the *intent* (which repos, what change, which branch) even
   without the diffs — and since `repos/` are real clones, an agent that
   learns a branch exists from `effort show` can go read it.
2. **Summaries describe trunk.** `summarize` works from the locked state, so
   branch work is invisible in the curated context until it lands. Long-lived
   branches degrade the workspace's core promise (the big picture is
   current).
3. **Checkout contention.** One clone, one working tree: two concurrent
   efforts cannot have the same repo on different branches. The "current
   effort" pointer is, de facto, also "whose branch set occupies the
   checkouts". **Operating assumption (confirmed in discussion): a workspace
   works one effort at a time when efforts overlap on a repo.** Worth stating
   in the workspace docs; today it is implicit.

## Agreed default: trunk-first, branch as the exception

Work directly on a repo's `main` unless one of three things forces a branch:

1. **Experiment** — work that may be discarded shouldn't pollute trunk
   history; deletion is the cleanup.
2. **Repo governance** — some editable repos only accept changes by PR; the
   branch is delivery plumbing, not isolation strategy. Keep it as
   short-lived as the slice it carries.
3. **Coordinated breaking change** — when landing straight to trunk in repo A
   breaks the contract with repo B until B catches up, and compatible
   sequencing isn't possible, stage both sides on branches and land together.

The decision is **per repo, per effort** — one effort can commit straight to
`main` in repo A (additive change) while staging an experiment on a branch in
repo B. Each contained clone makes the independence across repos total; the
only constraint is intra-repo (cost 3 above). Committing to trunk *is* the
per-slice landing, so the merge-back question dissolves in this mode.

## The `branch: null` vs `=main` ambiguity

When an effort deliberately works on trunk in a repo, the registry today
would say `branch: null` — ambiguous between "haven't decided yet" and
"deliberately trunk". The existing CLI already supports a cleaner record with
no code change: `effort set-branch <label> --repo <name>=main`. Because
`base` is computed as merge-base against the atlas ref, merge-base(main,
main) is main's head *at recording time* — so `base` becomes a stamp of where
on trunk the effort started, and `git diff <base>..main` shows the effort's
exact footprint in that repo at closeout.

**Candidate convention (docs-only change):** `branch: null` = touched,
undecided; `=main` = deliberately trunk, `base` = starting point. Two-line
clarification in `workspace_agents()` and `docs/workspace-format.md`.

## Ideas for parallel efforts on one repo (not commitments)

The serial assumption is fine for current use, but if concurrent efforts on
the same repo ever matter:

- **`git worktree`** — built into git; the CLI could materialize
  `repos/<name>` worktrees per effort branch. Cleanest conceptual fit, but
  opens questions: what does the lock describe, which path does the sandbox
  policy whitelist, which checkout do summaries read?
- **GitButler-style virtual branches** — multiple branches applied
  simultaneously to a *single* working dir, with hunks assigned to branches.
  Conceptually attractive for agent work (an agent could assign edits to the
  right effort), but it is a heavyweight dependency and GitButler is
  FSL-licensed source-available (each release converts to open source after
  two years), not OSI open source at release — fine to study, harder to
  embed.
- **Separate workspaces per effort** — already possible via `seed-from`;
  heavyweight on disk but zero new mechanism.

## Candidate next steps

1. Document the `=main` convention and the `branch: null` semantics
   (workspace `AGENTS.md` text in `workspace_agents()`, `docs/cli.md`,
   `docs/workspace-format.md`).
2. State the serial-efforts assumption (one effort at a time per overlapping
   repo) explicitly in the workspace docs.
3. If disposition tracking earns its keep: record per-repo landing
   (merged sha / PR / abandoned) at `effort close`.
4. Park worktree support until a real concurrent-efforts need appears; if it
   does, start a `docs/changes/` design doc.
