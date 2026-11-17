# Upgrade an existing Zentaizo workspace (experimental)

> Status: **experimental**. This procedure is the intended replacement for the
> retired `zentaizo update` CLI command, but the design will sharpen as it gets
> exercised against real workspaces. Treat each upgrade as a careful, reviewable
> migration — not a one-shot command — and expect to refine these steps as you
> discover what's missing.

## When to run this

Run it when a workspace's bundled files, which phase 1 below lists, have fallen
behind Zentaizo's current conventions and the user wants to reconcile.

The deterministic trigger is `zentaizo status`: its `Conventions:` line
compares the generation stamped in the workspace's `zentaizo.lock.json`
(`conventions` block) against the generation the installed zentaizo
generates. `behind` and `not tracked` both call for this skill; `current`
means there is nothing to do.

Symptoms that motivate running it:

- The user upgraded the `zentaizo` CLI and a `zentaizo create` of a fresh
  workspace produces different `AGENTS.md` / skills than what this workspace
  has.
- Plan files use frontmatter fields or filename patterns that the current
  templates no longer document.
- New convention sections exist upstream that this workspace has never had.
- The workspace predates the Claude `SessionStart` session-title hook and should
  adopt it with `zentaizo claude-hooks` after the current `zentaizo` executable
  is on PATH.

Do **not** run it for:

- A workspace for which `zentaizo status` reports `Conventions: current`. There
  is nothing to do.
- Trivial typo fixes in template prose. Just edit the workspace file directly.
- Adding the workspace's project-specific instructions. That's atlas curation
  or normal AGENTS.md editing, not a template upgrade.

## Pre-flight

0. Scope the pass by generations. Read the workspace's stamped generation
   (the `conventions` block in `zentaizo.lock.json`, also reported by
   `zentaizo status`) and the installed `CONVENTIONS_DELTAS` map in
   `src/zentaizo/cli.py` (next to `CONVENTIONS_GENERATION`). The map has one
   concise entry per generation; the entries between the stamped generation
   and the installed one are the conventions this pass must reconcile, so
   read them first and let them focus the diff phase. An unstamped
   workspace (`Conventions: not tracked`) gets the full reconciliation —
   diff everything.
1. Run `zentaizo validate`. Put failures that come from old conventions into
   the migration plan, and fix the others first. Run `zentaizo validate` again
   before `zentaizo upgraded`. The most common other failure is a dangling
   `path:` entry in `zentaizo.atlas.json` whose target was renamed or removed
   in earlier work. Fixing such failures up front keeps the upgrade diff
   narrow and the `## Outcome` honest about what changed.
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
- `README.md` — generated from the `workspace_readme()` function in
  `src/zentaizo/cli.py`.
- `CLAUDE.md` — `@AGENTS.md` (an import line; Claude reads `CLAUDE.md`, not
  `AGENTS.md`, and loads the import in full). Workspaces created before
  2026-06-09 have a prose pointer stub here instead and should be migrated to the
  `@AGENTS.md` import.
- `GEMINI.md` — the workspace pointer stub.
- `.gitignore` — created by `zentaizo create`.
- `.ignore` — created by `zentaizo create` (generation 7 and later). Its
  search block is CLI-managed; see § Known sharp edges.
- `skills/curate-atlas.md`, `skills/plan-and-implement.md`,
  `skills/plan-template.md`, `skills/effort-template.md`,
  `skills/report-template.md`, `skills/handoff-template.md` and
  `skills/brainstorming-template.md` — copied verbatim from
  `src/zentaizo/templates/skills/`.
- The seven `sessions/` subdirectory shells: `efforts/`, `brainstorming/`,
  `changes/`, `questions/`, `debugging/`, `handoffs/`, `reports/`.
- `sessions/efforts.json` — the effort registry (seeded with a `main` effort by
  a current `zentaizo create`). A pre-effort workspace will not have it; a
  pre-effort-doc workspace may have registry entries without `number`.
- `.claude/settings.json` — not overwritten as a template file, but a current
  workspace can merge the managed session-title hook with `zentaizo claude-hooks`.

Read both sides. Capture each delta. Do not edit yet.

### 2. Classify each delta

For every difference, decide which category it belongs to:

- **Template-ahead, adopt.** Zentaizo added or refined something the workspace
  should pick up (a new section in AGENTS.md, a new skill, a frontmatter field).
  Action: write the new template content into the workspace file.
- **Workspace-ahead, keep.** The workspace deliberately diverged for
  project-specific reasons (a custom section in AGENTS.md, a tightened rule, a
  project-specific note). Any workspace text that differs from the old
  template counts, whether it is a section, an edit to a skill, or a whole
  `README.md` that the owner rewrote. Action: preserve the workspace's
  content. If the divergence looks broadly useful, surface it to the user as a
  candidate to promote upstream into Zentaizo, but do not silently re-upstream
  it.
- **Both diverged.** Template and workspace both moved in the same area but in
  different directions. Action: ask the user. Do not guess.
- **Convention rename.** A frontmatter field, filename pattern, or directory
  layout changed shape (e.g. `YYYY-MM-DD-<slug>.md` → `<label>-NNNN-<slug>.md`,
  or the `branch_prefix:` frontmatter field → `label:`). Action: this is the
  most expensive case — it cascades into the next phase.
- **Branch-prefix → effort label (the current big rename).** Older workspaces
  named slices by a git-branch-derived prefix (`<branch_prefix>-NNNN-<slug>.md`,
  with `branch_prefix:`/`implementation_branch:`/`implementation_base:` in
  frontmatter). The current convention names slices by a CLI-allocated **effort
  label** recorded in `sessions/efforts.json`. Migrating means: (a) treat each
  distinct existing prefix as an effort; (b) build `sessions/efforts.json` with
  one entry per prefix — carry `implementation_branch:`/`implementation_base:`
  into that effort's per-repo `repos: {name: {branch, base}}` map; (c) rewrite
  each plan's frontmatter `branch_prefix:` → `label:` and drop the
  `implementation_*` fields; (d) rename existing handoffs from the old
  `<prefix>-NNNN-<role>.md` scheme to the per-slice-letter scheme
  `<label>-NNNN<letter>[-<role>].md`. Filenames themselves keep `<prefix>-NNNN-`
  as `<label>-NNNN-`, so `changes/`/`debugging/` files usually need a
  frontmatter rewrite but **not** a rename.
- **Effort registry → effort docs.** Older effort-registry workspaces may have
  `sessions/efforts.json` entries but no registry-owned `number` and no
  `sessions/efforts/NNNN-<label>.md` docs. Migrating means: (a) assign
  `number: 1` to `main`; (b) assign remaining efforts by their `created` order
  (fall back to current registry order if timestamps are missing or tied);
  (c) create `sessions/efforts/`; (d) backfill each doc from
  `skills/effort-template.md`, seeding the opening framing line from the
  registry `description`; (e) run `zentaizo edited <doc>` after human/AI prose
  edits; and (f) run `zentaizo validate` to confirm there are no orphan docs,
  duplicate numbers, missing docs, or unnumbered efforts.

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
- **Effort doc backfills.** If registry efforts lack `number`, list the exact
  number assigned to each label and the new doc path
  `sessions/efforts/NNNN-<label>.md`. The registry is the source of truth; do
  not allocate by scanning filenames.
- **Cross-references in bodies.** If renamed filenames are referenced by other
  files (plans link to other plans, brainstorming docs, questions, debugging),
  every reference needs updating. Mechanical substitution usually suffices but
  list each affected file so the user can spot collateral damage.
- **`zentaizo.atlas.json` schema bumps.** If the atlas schema changed, the
  atlas needs a corresponding migration. Surface this explicitly; atlas changes
  are higher-risk than session-file changes because they cascade through
  `zentaizo.lock.json` and `zentaizo fetch`.
- **Generation-specific steps.** If the pass crosses a generation listed under
  § Generation-specific steps below, add that generation's steps to the plan.
  They cover artifacts that a template diff does not show, such as files to
  delete.

Bundle the full migration list into a `sessions/changes/` plan. If the effort
registry already exists and is already numbered, allocate the plan with
`zentaizo next-change upgrade-zentaizo --label main`. If the registry exists
but lacks numbers, assign the numbers and backfill `sessions/efforts/0001-main.md`
first so the CLI can allocate safely; then create the migration plan under
`main`. If you are migrating *into* the effort convention, the registry won't
exist yet — write the numbered seed `efforts.json` by hand and backfill the
`main` effort doc so the plan file itself is named under the new shape. The
plan's `## Plan` section lays out every file affected and the verification the
user will use to confirm correctness.

One plan can cover several workspaces, as a fleet plan kept in one of them,
when every generation that the pass crosses changes only skills, the
generated `README.md`, and template text in the generated `AGENTS.md`. Each
workspace still gets its own diff, keeps its own text, runs
`zentaizo upgraded`, and gets its own commit.

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
- **Final step — always: run `zentaizo upgraded` in the workspace.** It
  re-stamps the lock's `conventions` block to the installed generation so
  the pass is durably recorded and `zentaizo status` reports the workspace
  as current. It also deletes the lock's retired `graph` block, if one is
  left. Like `zentaizo edited`, the stamp is CLI-written — never edit
  the block by hand.

## Generation-specific steps

Most deltas are template text, and the diff phase finds them. Some generations
also retire or move artifacts that no template produces, so a diff never shows
them, and some need care that a diff does not show. When the pass crosses one
of these generations, add its steps to the migration plan. A workspace that
missed several generations takes the steps of every generation it missed, in
order, before `zentaizo upgraded`.

### Generation 7: retired knowledge-graph artifacts

Generation 7 removed the knowledge-graph layer (`zentaizo graph`). Delete
these artifacts:

- `graphify-out/` — untracked derived output. Delete the directory. A
  workspace from before 0.10.3 may have committed parts of it: remove
  whatever `git ls-files graphify-out` lists with `git rm -r`.
- The root `.graphifyignore` — committed, and it carries the marker
  ``# Managed by `zentaizo graph`.``. Delete it with `git rm .graphifyignore`.
  A root `.graphifyignore` without the marker was written by the user, so ask
  before deleting it.
- `repos/.graphifyignore`, if a user wrote one — untracked, like everything
  under `repos/`. Before deleting it, move its vendored-path lines into the
  `search_exclude` list of the matching repo entry in `zentaizo.atlas.json`,
  written relative to that repo's root.

Also delete the `graphify-out/` line from `.gitignore`. Leave the lock's
`graph` block alone: the final `zentaizo upgraded` deletes it.

### Generation 7: root searches see `repos/`

Generation 7 also takes `repos/` out of `.gitignore`, so that `rg` and
Claude Code's `grep` search the repos from the workspace root. Each clone's
`.git/info/exclude` hides `repos/` from git instead. A CLI-managed block in
the committed `.ignore` shows `repos/` to `rg`, and a repo's
`search_exclude` list in the atlas keeps vendored code out of both tools'
results. Take these steps in this order:

1. Run `zentaizo fetch`, in any form, such as `zentaizo fetch --repo NAME`.
   It adds `/repos/` to `.git/info/exclude` and writes the `.ignore` block.
   Do not edit `.gitignore` before this step: without the exclude line,
   `git status` lists every repo as untracked.
2. Delete the `repos/` line from `.gitignore`. In its place, after the
   `docs/snapshots/*.flagged.*` line, add this comment line:

   ```text
   # repos/ is hidden from git by .git/info/exclude, which `zentaizo fetch` writes.
   ```

3. Add `search_exclude` items to the atlas for vendored trees, such as a
   copy of a library inside a repo. Write each item relative to its repo's
   root, for example `"search_exclude": ["third_party/boost/"]`, and include
   the lines from any `repos/.graphifyignore` (see the previous subsection).
   Then run `zentaizo fetch` again. It writes the vendored paths into the
   blocks in `.ignore` and `.gitignore`.
4. Check that `git status` lists nothing under `repos/`, and that
   `zentaizo status` reports `Search: current`. If `status` names symlinked
   repos, tell the owner that root searches skip them. Replacing a symlink
   with a clone or a git worktree is the owner's choice.
5. Tell the owner to run `zentaizo fetch` in every other clone of this
   workspace right after pulling this change. Until then, `git status` in
   that clone lists every repo as untracked, and `git add -A` there would
   add each repo as an embedded repository. `zentaizo status` in that clone
   reports `Search: exclude missing`.

### Generation 7: a trimmed `AGENTS.md`

Generation 7 also trims the generated `AGENTS.md` to facts and invariants.
Its session-filename table, its `edited_by` details and its delegation steps
move to § Reference in `skills/plan-and-implement.md`. The `AGENTS.md`
subsections "Editor attribution" and "Filename Convention" and the section
"From Brainstorming to Plan" are gone. The diff phase shows the new text;
these two steps need care:

1. Adopt the new `AGENTS.md` text section by section. Keep each
   workspace-specific section, and keep the repo-roles block as § Known sharp
   edges says. When the workspace and the template both changed a section,
   ask the user.
2. Search the workspace-specific text that stays for references to the three
   removed sections, such as "§ Filename Convention". Point each one at the
   matching subsection of § Reference in `skills/plan-and-implement.md`.

### Generation 8: the use first, reviews and a paused state

Generation 8 changes four skills, two passages of the generated `README.md`,
and one paragraph of the generated `AGENTS.md`. Keep the workspace's own text
in each of them, as § 2 says for workspace-ahead text.

1. Copy `skills/effort-template.md`, `skills/plan-template.md`,
   `skills/plan-and-implement.md` and `skills/handoff-template.md` from the
   templates.
2. In `README.md`, adopt the new sentence about the atlas and the lock under
   § Layout, and the new opening of § First Step.
3. In `AGENTS.md` § Recording Work in `sessions/`, add the paragraph that
   starts "Fit each plan and each review", right after the paragraph that
   starts "`skills/plan-and-implement.md` gives the procedure".

The paused state needs no migration. Efforts and slices keep their status,
and existing plans and effort docs need no new sections.

## Boundaries — what this procedure does NOT do

- It does not silently rewrite the workspace. Every change is staged through
  the plan and visible in `git diff` before any commit.
- It does not modify code in editable repos. Convention changes are about the
  workspace shell — `AGENTS.md`, `skills/`, `sessions/`, the atlas. The
  editable repos themselves are out of scope.
- It does not commit on the user's behalf unless they authorize it.
- It does not rewrite `zentaizo.lock.json`'s resolved sources on its own.
  Its only direct lock changes are the two that `zentaizo upgraded` makes at
  the end: the `conventions` re-stamp and, for a workspace from before
  generation 7, the deletion of the retired `graph` block. The `zentaizo
  fetch` runs in the generation-7 search steps also refresh the lock, as any
  fetch does, so run them under the user's supervision. If another fetch
  refresh is needed after the migration (e.g. because a repo URL or ref
  shape changed), run `zentaizo fetch` separately under the user's
  supervision.

## Known sharp edges

This skill is new. Things that are likely to bite and that should refine the
procedure over time:

- **The repo-roles block in `AGENTS.md` is CLI-managed.** The section between
  `<!-- BEGIN zentaizo repo-roles -->` and `<!-- END zentaizo repo-roles -->` is
  written by `zentaizo fetch` from the atlas. It is not a workspace-local
  addition and not template text: keep it verbatim, with its markers, wherever
  the reconciled `AGENTS.md` places it, and never merge it by hand. If it is
  stale or missing, `zentaizo fetch` fixes it.
- **The search blocks in `.ignore` and `.gitignore` are CLI-managed.** The
  lines between `# BEGIN zentaizo search` and `# END zentaizo search` are
  written by `zentaizo fetch` from the atlas, like the repo-roles block.
  Keep them verbatim, and change `search_exclude` in the atlas instead. The
  `.gitignore` lines outside the block are template-owned.
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
