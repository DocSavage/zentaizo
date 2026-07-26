# The Session Model: Efforts, CLI-Allocated Slices, and the Editor Ledger

_Distilled design doc — current architecture + rationale._

## What it is

The session model is the part of Zentaizo that turns "doing work in a Zentaizo workspace"
into a durable, auditable trail under `sessions/`. It rests on one move: every
deterministic chore an agent would otherwise re-derive from prose each session —
naming a body of work, allocating the next filename, computing a counter,
formatting a timestamp, recording who edited a file — is handed to the CLI, while
prose and judgment stay with the agent. The unit of work is an **effort**: a
named body of related work that may span several editable repos, with a registry
entry for its machine state and a plan doc for its prose. Efforts decompose into
numbered **slices** (`changes/` plans and `debugging/` notes), which the CLI
names and scaffolds; supporting artifacts (handoffs, reports, Q&A logs,
brainstorming inputs) hang off the same scheme.

The design principle throughout is *deterministic in the CLI, judgment in the
AI*. Counter arithmetic, uniqueness, merge-base computation, and template
instantiation are mechanical and live in code; choosing an effort word, writing a
plan, and deciding which repos a slice touches are judgment and stay with the
agent. The CLI is treated as a prerequisite, not an accelerator — there is no
"name a file by hand" fallback, because removing the procedure prose entirely is
the strongest defense against an LLM replaying a deterministic rule
non-deterministically (the failure mode the model is built to avoid).

## Architecture

### The effort: registry state plus a plan doc

An effort has two orthogonal facets joined by its **label** as the key, with a
single source of truth per field so the facets cannot drift:

- **Machine state** lives in `sessions/efforts.json` (the registry). Each entry
  carries `label`, an integer `number`, a one-line `description`, `status`
  (`open`/`closed`), a `repos` map of `{ name: { branch, base } }`, and
  `created`/`updated` timestamps. The registry also tracks `current` — the
  effort that `next-*` and `path` default to, the deterministic
  git-`HEAD`-analogue that replaces "the checked-out branch" as the signal for
  *which effort am I on*. Schema in `new_efforts_registry()` / `_main_effort()`
  (`src/zentaizo/cli.py`).
- **Prose** lives in `sessions/efforts/NNNN-<label>.md` (the effort plan doc) —
  the 10,000-ft plan a body of work is shaped around before it is sliced. Its
  frontmatter is deliberately minimal (`created` + `edited_by` only); status, the
  branch map, and the number are registry-owned. The template
  (`src/zentaizo/templates/skills/effort-template.md`) is lean: a framing line
  then `Shape of the solution` / `Constraints & appetite` / `Non-goals /
  deferred` / `Open questions` / `Phasing & related efforts`.

The number is **registry-owned and allocated** by `allocate_effort_number()` as
`1 + max(existing registry numbers)`; the filesystem is never the allocator. A
read derives the doc path from `number` + `label` (`effort_doc_path()`), so the
two facets reference each other by name exactly the way slices already join to
the registry by label. No branch or base ever lands in the doc, which keeps the
minimal line-based frontmatter reader (`read_frontmatter()` — not a YAML parser)
free of nested maps.

Division of authority is exact: the **registry** owns effort identity, the
per-repo branch/base, and the effort number; the **filesystem** owns slice
numbering. The registry deliberately does *not* store the slice counter, so
creating a slice never writes the registry — keeping it a low-frequency,
low-conflict file (written only by `effort new` / `set-branch` / `close` /
`switch` — `switch` moves the `current` pointer, which is registry state). Of a
slice's frontmatter, only `label` and `editable_repos` name the effort and its repos;
`status`, `created`, `short_title`, `edited_by`, and the optional `related` complete
the template (`templates/skills/plan-template.md`). The branch and base are looked up
from the registry, never duplicated into the plan.

### `main` is the deliverable trunk

`main` is the pre-seeded effort that exists at workspace bootstrap, special by
*role* rather than content — the trunk that work flows into until a divergence
warrants branching, exactly like git `main`. It is `number` 1
(`MAIN_EFFORT_DESCRIPTION = "Principal line of work: the deliverable trunk."`),
gets `0001-main.md` at creation, and is uncloseable — `effort_close()` refuses
`main` explicitly rather than only documenting the rule. It is otherwise a normal
effort: it can carry slices and record editable repos it touches (with
`branch: null` until a feature branch opens).

### The `effort` command group

`effort` (`effort_new` / `switch` / `show` / `list` / `set_branch` / `close`,
all in `src/zentaizo/cli.py`) manages the registry and reads its state:

- **`effort new [label]`** is the constructor and the step that captures intent.
  It allocates the registry number, normalizes or (with no label)
  deterministically suggests a word from `THEMED_LABELS` via
  `allocate_themed_label()`, refuses a label already in the registry *or* in use
  on disk (`label_in_use_on_disk()`), scaffolds the doc, stamps `created` and the
  first `edited_by` entry, records any `--repo` branches, makes the effort
  `current`, and prints the doc path. `--describe` sets the canonical short
  description and also seeds the doc's framing line as scaffold text only (not a
  maintained mirror).
- **`effort switch`** repoints `current` (the git-checkout analogue).
- **`effort show` / `list`** are the read verbs for "what is this effort, which
  repos/branches, which slices?" and "what efforts exist / which is current?".
  `show` resolves and requires the doc path; both degrade gracefully on a legacy
  effort without a number, marking it `(needs upgrade)`.
- **`effort set-branch`** records repo participation against an existing effort.
  `--repo NAME=BRANCH` records a real branch and computes the base; bare
  `--repo NAME` attaches a repo with `{branch: null, base: null}` (how `main`
  attaches a repo before a branch exists) but **refuses to erase** an
  already-recorded branch, consistent with fail-loud.
- **`effort close`** flips `status` to `closed` (refusing `main`). A closed
  effort is refused for writes but still readable.

`base` is machine-computed, never guessed: `compute_base()` runs
`git merge-base <branch> <atlas-ref>` (short SHA) when the repo is fetched and the
branch exists, else leaves it `null`. The CLI never *creates* a branch — git
mutation stays out; it only records the branch the user opened.
`validate_effort_repo()` enforces that a referenced repo exists in the atlas and
is `role: edit` (skipped before an atlas exists, so the commands work in a fresh
workspace).

### CLI-allocated slice and session paths

`path` (read, never writes) and `next-*` (allocate + scaffold) share one
resolver core over the registry and `sessions/`. Both default to the `current`
effort; `--label` overrides; `next-*` prints which effort it used so the choice is
never silent.

Slice filenames are `<label>-NNNN-<slug>.md`. The counter is **unified across
`changes/` and `debugging/`** — one sequence per label — so a change and a
debugging note never reuse a number (`next_counter()` over `scan_slice_files()`,
which globs both dirs with `_slice_pattern()` = `^<label>-(\d{4})-`; the `-\d{4}-`
shape means `do` never cross-matches `dojo`). There is **no cross-branch
collision check** — uniqueness is guaranteed at reservation time by `effort new`,
and full agent-chosen words don't truncate-collide.

- **`next-change` / `next-debugging`** consume the shared counter and scaffold
  from `plan-template.md` (`_next_slice()`); `next-debugging` reuses the same
  plan-shaped template deliberately (a debugging note is "a plan for an
  investigation"). `--short-title` fills the `short_title` frontmatter (capped at
  `SHORT_TITLE_MAX`), the field the Claude session-title hook reads.
- **`next-handoff <id> [topic]`** reuses the slice id (never the counter) and
  auto-allocates a per-slice letter `a`–`z` via `next_handoff_letter()` — the
  uniqueness key — with an optional, non-load-bearing topic slug. For `id != 0000`
  it verifies a paired plan exists and refuses an orphan handoff; `0000` is the
  untied (restart/multi-slice) handoff and skips that check.
- **`next-brainstorming` / `next-note` / `next-report`** don't touch the counter
  or an effort. `next-brainstorming` writes a provenance-bearing
  `YYYY-MM-DD-<slug>.md` under `brainstorming/` (which otherwise stays a permissive
  home for raw, frontmatter-free dumps); `next-note` a dated Q&A stub under
  `questions/`; `next-report` a living `<slug>.md` under `reports/`.

Reads recover what the agent forgot. `path slice <id>` globs both slice dirs and
must resolve to exactly one file (`padded_id()` accepts a bare `43` or `0043`;
ambiguity across dirs is fail-loud); `path slice --next` previews the next stem
without writing; `path effort` resolves the effort doc; `path handoff <id>` lists
a slice's handoffs in letter order. **`path active`** (`find_active_plan()`) is
defined exactly: of the `changes/` files for the effort, drop any whose `status`
is in `CLOSED_SLICE_STATUSES`, then take the highest counter — so a plan stops
being "active" the moment closeout marks it terminal (`debugging/` is excluded;
"active" means the implementation plan).

All creators write with `_write_exclusive()` (exclusive-create, refusing to
clobber and losing cleanly on a same-instant double-run) and emit a uniform
`--json` shape via `_emit_created()`. Same-effort concurrency (two agents both
computing `NNNN+1`) is an accepted, out-of-scope race; the low-frequency registry
is not a hotspot, and git worktrees are the escape hatch.

### Slice statuses

Statuses are free-form strings; the only behavior is membership in
`CLOSED_SLICE_STATUSES = {"done", "superseded", "abandoned"}` (`src/zentaizo/cli.py`),
which `path active`/`find_active_slice()` and the `short_title` warning check key
on. `superseded` distinguishes *work continued under a successor plan* from
`abandoned` (*work we decided not to do*); the CLI handles all three identically
wherever "closed" matters, including `effort show`'s per-slice status display.

### The handoff / restart loop

A handoff is execution glue, not part of a plan's lifecycle. The
`plan-and-implement.md` skill describes the planner/implementor split: after the
user approves a plan (still `planned`), run `next-handoff <id> [agent]`, write a
self-contained prompt (the whole file below the frontmatter *is* the prompt,
handed off by reference), and the implementing agent reads `AGENTS.md` + plan +
handoff, flips the plan to `in-progress`, and executes. Repeated restarts use
`next-handoff <id> resume` (or `restart`/`diagnosis`), each auto-advancing the
letter so handoffs never collide and never consume the slice counter. Incoming
sessions can rediscover the target with `path active` (the open slice) and
`path handoff` (the latest letter), so a thin "implement the handoff" signal is
enough to resume.

### Editor attribution: the `edited_by` ledger

Frontmatter-bearing session files (`efforts/`, generated `brainstorming/`,
`changes/`, `debugging/`, `reports/`, `handoffs/`) carry an `edited_by:` ledger —
git-style local-timestamped entries recording who crafted, reviewed, or modified
the file, in order; the latest entry is the effective last-modified time (there is
no `updated:` field on slices). Every scaffolder of a frontmatter-bearing file
stamps the first entry (`_record_edited_by()` after `_write_exclusive()`), while
`next-note` deliberately writes a frontmatter-free Q&A stub and stamps nothing
(`next_note()`); `zentaizo edited <path>`
appends a later one, or *refreshes in place* when the most recent entry is the
same editor (a run of edits by one editor collapses to one line —
`_stamp_edited_by()`).

The identity is resolved deterministically, never hand-written by the model:
`resolve_editor_identity()` takes an explicit `--as` override, else the active AI
agent, else the human `git config user.name`. The AI identity comes from the
**same commit-trailer cache** the bundled `prepare-commit-msg` hook and
`zentaizo commit-trailer` read — the exact model plus reasoning effort — with a
Codex-config fallback that populates that cache when missing. This keeps the
recorded model honest (a model cannot reliably name its own id) and keeps the
ledger consistent with commit attribution.

### Integrity and migration

The registry owns the number; the filesystem is checked against it, never trusted
to allocate. `zentaizo validate` runs `effort_doc_integrity_errors()` —
fail-loud detection of a missing registry file, a registry effort with no doc, an
orphan doc with no registry entry, duplicate numbers, an invalid doc filename, and
legacy efforts lacking a number — reporting but never auto-fixing. Targeted checks
also fire on the specific operation (`require_effort_doc_path()`,
`ensure_effort_numbers_allocatable()` refusing a new number when an effort lacks
one). `load_efforts()` degrades a pre-CLI workspace gracefully by synthesizing an
in-memory `main` effort (writing nothing); the broad **reconcile** — backfilling
docs, assigning numbers, renaming legacy files — is delegated to the AI-driven
`upgrade-zentaizo` skill, not a one-shot CLI overwrite, because convention bumps
routinely touch frontmatter, filenames, and cross-references.

### How it composes into the before/after trail

The directories model the arc of a decision (see `docs/workspace-format.md`
§ Sessions): `brainstorming/` is pre-decision input; an **effort** distills that
into a plan doc; the effort decomposes into `changes/` slices (and `debugging/`
investigations) that the CLI names and scaffolds; `handoffs/` carry a slice across
context resets; `questions/` and `reports/` capture cross-cutting Q&A and
syntheses. `current` plus the registry — not a git branch — is the durable answer
to "which work is live," and the `edited_by` ledger threads provenance through
every frontmatter-bearing file.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Unit of work | An **effort** (label-keyed), not a git branch | One body of work can span several editable repos on differently-named branches; a branch is mutable and 1:1 with neither |
| Effort identity source | A CLI-reserved **label** in `sessions/efforts.json`, agent-chosen (themed-word fallback) | Collapses the whole branch→prefix derivation + cross-branch collision subsystem; uniqueness is guaranteed at reservation |
| Effort plan home | The effort *is* its doc (`sessions/efforts/NNNN-<label>.md`) | A separate "brief" would be 1:1 with the effort — terminology bloat; collapse instead of add |
| `main` | The uncloseable deliverable trunk (enforced) | Every reader already reads `main` as "principal line of work"; the trunk/branch model matches how developers think |
| Number allocation | Registry-owned (`1 + max`); filesystem is an integrity check only | Single source of truth per field; the filesystem can't silently mis-allocate |
| Slice counter | One shared counter across `changes/` + `debugging/`, filesystem-derived | A change and an investigation never reuse a number; keeps the registry untouched by slice creation (low-conflict) |
| No `next-effort` | `effort new` is the constructor | An effort is the parent of slices and already owns a lifecycle namespace; `next-effort` would re-split the collapse |
| `base` field | Machine-computed via `merge-base`, else `null` | The one judgment field the CLI fills — only because it comes from real git state, never inferred |
| Handoff uniqueness | Per-slice letter `a`–`z` (lowercase only), reusing the slice id | Case-insensitive filesystems make uppercase a latent collision; the optional topic stays non-load-bearing |
| `path active` keys on status | Drop `CLOSED_SLICE_STATUSES`, take highest counter | A finished plan stops being active the instant closeout marks it terminal |
| Editor identity | Resolved from the shared commit-trailer cache, never hand-written | A model can't reliably name its own id; keeps `edited_by` consistent with commit attribution |
| Existing-workspace migration | Delegated to the `upgrade-zentaizo` skill, not a CLI command | Convention bumps touch frontmatter/filenames/cross-refs — reconciliation is an AI-driven plan, not an overwrite |

## Considered and not taken

- **Branch-derived filename prefixes** (the original design) — a
  `derive_prefix()` truncation rule, `--branch`/`--prefix` precedence, a
  detached-HEAD refusal, and a cross-branch collision check. All deleted: the
  coupling to a single branch was wrong once an effort can span repos.
- **A separate "brief" artifact** for an effort's big-picture plan — rejected as
  1:1 terminology bloat; the effort's doc is its brief.
- **A `zentaizo new change|effort|…` namespace** unifying the verbs — rejected as
  churn that doesn't reduce concept count (`effort` still needs its own management
  namespace).
- **Storing the slice counter in the registry** — rejected; it would make every
  slice creation a registry write and a concurrency hotspot.
- **Lifecycle-managing `brainstorming/`** or a `--source-type` flag / `related`
  consumption / a `path brainstorming` resolver — deferred; the directory stays
  permissive and brainstorming links stay advisory until real usage justifies
  schema.
- **Status enforcement** — rejected; statuses stay free-form strings,
  `CLOSED_SLICE_STATUSES` membership is the only behavior.
- **Automating the restart itself** — out of scope; the user still opens the fresh
  session and gives a thin signal, no conversational state leaves the committed
  files.

## See also

- `docs/cli.md` — the `effort` / `path` / `next-*` / `edited` / `validate`
  command reference.
- `docs/workspace-format.md` § Sessions — the directory layout and the
  before/after trail.
- `docs/design/foundations.md` — source roles, atlas-vs-lock, and the template
  feedback loop this builds on.
- `src/zentaizo/cli.py` — the resolver core, the `effort`/`path`/`next-*`
  commands, `CLOSED_SLICE_STATUSES`, and the `edited_by` ledger helpers.
- `src/zentaizo/templates/skills/` — `effort-template.md`, `plan-template.md`,
  `handoff-template.md`, and `plan-and-implement.md` (the plan → execute →
  close-out lifecycle).
- `README.md` — the build-context-then-work-in-efforts walkthrough.
