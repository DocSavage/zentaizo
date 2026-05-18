# Upgrade an existing Zentaizo workspace (experimental)

> Status: **experimental**. This procedure is the intended replacement for the
> retired `zentaizo update` CLI command, but the design will sharpen as it gets
> exercised against real workspaces. Treat each upgrade as a careful, reviewable
> migration — not a one-shot command — and expect to refine these steps as you
> discover what's missing.

## When to run this

Run it when a workspace's bundled files (`AGENTS.md`, `skills/curate-atlas.md`,
`skills/plan-and-implement.md`, `skills/plan-template.md`, `CLAUDE.md`,
`GEMINI.md`, the `.gitignore`, and the `sessions/` subdirectories) have fallen
behind Zentaizo's current conventions and the user wants to reconcile.

Symptoms that motivate running it:

- The user upgraded the `zentaizo` CLI and a `zentaizo create` of a fresh
  workspace produces different `AGENTS.md` / skills than what this workspace
  has.
- Plan files use frontmatter fields or filename patterns that the current
  templates no longer document.
- New convention sections exist upstream that this workspace has never had.

Do **not** run it for:

- Workspaces whose `AGENTS.md` matches the current template byte-for-byte. There
  is nothing to do.
- Trivial typo fixes in template prose. Just edit the workspace file directly.
- Adding the workspace's project-specific instructions. That's atlas curation
  or normal AGENTS.md editing, not a template upgrade.

## Pre-flight

1. Run `zentaizo validate` in the workspace and resolve anything it reports
   **before** starting the upgrade. The most common pre-existing issue is
   dangling `path:` entries in `zentaizo.atlas.json` whose targets were
   renamed or removed in earlier work. Integrity bugs in the workspace are
   not part of an upgrade's scope — fixing them up front keeps the upgrade
   diff narrow and the `## Outcome` honest about what changed.
2. Confirm the workspace is clean in git (`git status` shows no unstaged
   changes), or that the user understands the upgrade will land alongside their
   existing work-in-progress.
3. Confirm the user has the current Zentaizo source available. The procedure
   needs to read the installed templates for comparison. If `zentaizo skills
   install` was used as a symlink, the source is wherever that symlink points;
   otherwise it's the `templates/` directory inside the installed `zentaizo`
   package.

## Procedure

The upgrade is a four-phase plan: **diff → classify → migrate → execute**.
Write each phase to the user before doing it, the same way `plan-and-implement.md`
treats a normal change.

### 1. Diff the templates against the workspace

Compute the current template output and diff against the workspace's files. The
files Zentaizo owns are:

- `AGENTS.md` — generated from the `workspace_agents()` function in
  `src/zentaizo/cli.py`.
- `CLAUDE.md`, `GEMINI.md` — the workspace pointer stub.
- `.gitignore` — created by `zentaizo create`.
- `skills/curate-atlas.md`, `skills/plan-and-implement.md`,
  `skills/plan-template.md` — copied verbatim from
  `src/zentaizo/templates/skills/`.
- The four `sessions/` subdirectory shells: `brainstorming/`, `changes/`,
  `questions/`, `debugging/`.

Read both sides. Capture each delta. Do not edit yet.

### 2. Classify each delta

For every difference, decide which category it belongs to:

- **Template-ahead, adopt.** Zentaizo added or refined something the workspace
  should pick up (a new section in AGENTS.md, a new skill, a frontmatter field).
  Action: write the new template content into the workspace file.
- **Workspace-ahead, keep.** The workspace deliberately diverged for
  project-specific reasons (a custom section in AGENTS.md, a tightened rule, a
  project-specific note). Action: preserve the workspace's content. If the
  divergence looks broadly useful, surface it to the user as a candidate to
  promote upstream into Zentaizo, but do not silently re-upstream it.
- **Both diverged.** Template and workspace both moved in the same area but in
  different directions. Action: ask the user. Do not guess.
- **Convention rename.** A frontmatter field, filename pattern, or directory
  layout changed shape (e.g. `prototype_base_commit:` → `implementation_base:`,
  or `YYYY-MM-DD-<slug>.md` → `<branch_prefix>-NNNN-<slug>.md`). Action: this
  is the most expensive case — it cascades into the next phase.

Output a written classification for the user before going further. The user's
sign-off here is what authorizes the migration phase.

### 3. Plan artifact migrations

For every **convention rename** identified above, walk the existing
`sessions/` files and list every change required:

- **File renames.** If filename conventions changed, every existing file in the
  affected directories needs a new name. Compute each new name deterministically
  from the workspace's branch history if possible; ask the user to resolve
  ambiguities. Renames must be done with `git mv` so history is preserved.
- **Frontmatter rewrites.** If field names changed, every plan/debugging file
  with the old field needs a key rename. List the files; do not modify yet.
- **Cross-references in bodies.** If renamed filenames are referenced by other
  files (plans link to other plans, brainstorming docs, questions, debugging),
  every reference needs updating. Mechanical substitution usually suffices but
  list each affected file so the user can spot collateral damage.
- **`zentaizo.atlas.json` schema bumps.** If the atlas schema changed, the
  atlas needs a corresponding migration. Surface this explicitly; atlas changes
  are higher-risk than session-file changes because they cascade through
  `zentaizo.lock.json` and `zentaizo fetch`.

Bundle the full migration list into a `sessions/changes/` plan using the
current workspace's filename convention (or, if that convention is itself being
upgraded, use the *new* convention so the plan file itself documents the new
shape). Title it something like `<branch_prefix>-NNNN-upgrade-zentaizo-<date>.md`.
The plan's `## Plan` section lays out every file affected and the verification
the user will use to confirm correctness.

### 4. Execute on approval

Once the plan is approved by the user, follow `plan-and-implement.md`'s
executing-the-plan procedure exactly. Specifically:

- Mark the plan `in-progress`.
- Apply changes in the order: file content overwrites first (template-ahead
  cases), then convention-rename frontmatter rewrites, then file renames last
  (so cross-references can be fixed before the filenames they point at move).
- After each batch, re-run any workspace-level checks the user has (typically:
  `git diff` review, plus any project-specific tests in editable repos).
- Close out the plan with a `## Outcome` section that lists what was actually
  changed, any deltas you classified as "workspace-ahead, keep" so future
  upgrades remember why, and any items that should be promoted upstream.

## Boundaries — what this procedure does NOT do

- It does not silently rewrite the workspace. Every change is staged through
  the plan and visible in `git diff` before any commit.
- It does not modify code in editable repos. Convention changes are about the
  workspace shell — `AGENTS.md`, `skills/`, `sessions/`, the atlas. The
  editable repos themselves are out of scope.
- It does not commit on the user's behalf unless they authorize it.
- It does not upgrade `zentaizo.lock.json`. If a fetch refresh is needed after
  the migration (e.g. because a repo URL or ref shape changed), run
  `zentaizo fetch` separately under the user's supervision.

## Known sharp edges

This skill is new. Things that are likely to bite and that should refine the
procedure over time:

- **Section-level merging in `AGENTS.md` is approximate.** Diffing whole files
  works for unchanged-or-completely-replaced sections. For sections that have
  been edited on both sides, asking the user is currently the only safe answer.
- **Filename conflicts.** If a rename target already exists (because the
  workspace independently used the same name), surface it before any `git mv`.
- **No rollback story beyond git.** The migration's safety net is the user's
  git history. Run on a clean tree where possible; encourage the user to commit
  the plan file *before* execution so the migration itself is a reviewable
  commit.
- **The skill itself can drift.** If Zentaizo conventions change in a way that
  this skill doesn't anticipate, surface that gap to the user instead of
  papering over it.
