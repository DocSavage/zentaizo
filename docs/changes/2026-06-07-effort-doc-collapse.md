---
created: 2026-06-07
status: implemented
implemented: 2026-06-07  # 58e1310
edited_by:
  - 2026-06-07  Claude Opus 4.8
  - 2026-06-07  Codex gpt-5.5
---

# Efforts get a plan doc: collapsing "brief" into the effort

_Design doc. Drafted 2026-06-07. Sequel to [`next-slice-cli-helper.md`](2026-05-27-next-slice-cli-helper.md): that design gave an effort a **name** (a CLI-allocated label backing a `sessions/efforts.json` registry); this one gives the effort a **body** — a human-authored plan doc — and corrects what `main` means. Status: implemented 2026-06-07 in the CLI, templates, docs, and tests. **Revised 2026-06-07 after a Codex review:** `main` is uncloseable (enforced); the **registry** owns the effort number (filesystem scan demoted to an integrity check); repo attachment to `main` is defined via a relaxed `set-branch`; `--describe` seeds the doc as scaffold only; integrity/migration failure modes are made explicit. Further refined after a second Codex pass (signed off): bare `set-branch` never downgrades an existing branch, and orphan / duplicate-number detection lives in `zentaizo validate`._

An effort today is a registry entry with a one-line `description` and a repo→branch/base map, and nothing else. There is no structured home for the *why/what* of a body of work — the 10,000-ft plan that a project is shaped around before it is sliced into `changes/`. This design adds that home as `sessions/efforts/NNNN-<label>.md`, collapses the would-be separate "brief" concept into the effort itself, and corrects the `main` effort from a "workspace-meta only" bucket (a never-validated framing that practice contradicted) to what everyone already reads it as: the deliverable trunk.

## Problem

Three gaps, one root.

1. **A project's big-picture plan has no home.** Sessions has `brainstorming/` (freeform input *before* a decision), `changes/` (implementation slices), `debugging/` (plan-shaped investigations), `reports/` (synthesized output *after*, with a conclusion), `handoffs/` (execution glue). None of these is "the 10,000-ft plan we're building toward and will decompose into slices." Today that plan either rots in chat or gets wedged into a freeform brainstorming file with no schema and no provenance.

2. **An effort has no structured intent.** The registry entry carries a one-line `description` and the branch map — useful machine state, but no place for problem/motivation, solution shape, constraints, non-goals, or open questions. The reasoning behind a body of work lives nowhere durable.

3. **`main` is mischaracterized.** `MAIN_EFFORT_DESCRIPTION` (`cli.py:2031`) and the generated instructions call `main` *"workspace-meta work: atlas, summaries, conventions — not tied to an editable repo."* Practice contradicts this: in the flagship `zen-segmend-mesher` workspace the **primary meshing implementation lived under `main`**, on the working branch, and the adaptive-dual-contouring → marching-cubes pivot was the *first* divergence that warranted a separate branch / second effort. The narrow charter was an aspiration codified before it was validated; the word `main` means "the principal line of work" to every reader, yet the docs point it at its own inverse.

The naive fix to (1)+(2) would be a separate **"brief"** artifact. But a brief would be 1:1 with an effort — two concepts, two commands, two things to keep in sync, for one body of work. That is terminology bloat. The fix is to **collapse**, not add.

## The fix: the effort's plan doc *is* the brief

There is no "brief" noun. An effort is **one concept** with **two orthogonal facets**, joined by the effort label as the key (exactly the way `changes/` slices already join to the registry by label — sharing a name is the existing pattern, not a new risk):

| Facet | Nature | Home |
|---|---|---|
| **git / branch** | machine-written, volatile | `sessions/efforts.json` — repos→{branch, base}, the `current` pointer, `open`/`closed` status, the effort `number` |
| **planning** | human-written prose | `sessions/efforts/NNNN-<label>.md` — the plan |

The two never overlap. **Single source of truth per field**, so the facets can't drift: `status` stays in the registry (the CLI gates writes on it via `effort close`); the doc's frontmatter is slice-minimal (`created` + `edited_by` only); the one-line `description` stays in the registry as the short label while the doc holds the full prose (different granularities, not duplication). No branch/base ever lands in the doc — keeping the line-based frontmatter reader (which is deliberately *not* a YAML parser) free of nested maps.

This also makes the model isomorphic to how developers already think: **`main` is the trunk; a new effort is a branch off it, spun up exactly when a developer would branch** (the dual-contouring→marching-cubes moment). A small project never leaves `main` — its entire planning surface is `sessions/efforts/0001-main.md` plus its slices. Bigger work adds `0002-…`, `0003-…` beside it. One uniform rule, no special cases.

## Design principles

Inherits the four from `next-slice-cli-helper.md` (deterministic-in-the-CLI / judgment-in-the-AI; the CLI is a prerequisite with no by-hand fallback; thin/stdlib-only; fail loud). Adds:

5. **Single source of truth per field.** Each piece of effort state has exactly one home. The registry owns volatile machine state (including the effort `number`); the doc owns prose. No mirroring.
6. **Minimize terminology; collapse before adding.** A new artifact must earn a new noun. The effort's plan is the effort's doc — not a "brief."
7. **Creation follows the object's kind.** An effort is the *parent* of the `next-*` child docs (which take its label and counter), not a peer. It already owns a lifecycle namespace (`effort switch/show/list/set-branch/close`), so its constructor stays `effort new` — extended to scaffold the doc. We do **not** add `next-effort`: it would duplicate `effort new` and re-split the collapse. `effort new` : effort :: `next-change` : change.

## Core change: `sessions/efforts/NNNN-<label>.md`

- **A new session subdirectory**, `sessions/efforts/`, added to the `create_workspace` dir list (`cli.py:643`) and seeded with `0001-main.md` right after `efforts.json` is written (`cli.py:658`).
- **Numbered globally; the registry owns the number.** Each effort carries a `"number"` field in `sessions/efforts.json`; `effort new` allocates it as `1 + max(existing registry numbers)` (seeded `main` is `1`, so the first new effort is `2`). The number orders the docs (`0001-main.md`, `0002-vastdb.md`, `0003-openshift-scalable-api.md`) and is allocation order — `0001` is naturally the umbrella/overall plan. The word label still prefixes the effort's child slices (`vastdb-0001-…`). **Reads derive the path** (`path effort`, `effort show`) from `number` + `label`; the filesystem is never the allocator (see *Integrity & migration failure modes*).
- **No collision with slices.** `_slice_pattern` is `^<label>-\d{4}-` and `scan_slice_files` only scans `changes/`+`debugging/` (`cli.py:2138`, `2144`). Effort docs are `NNNN-<label>.md` (number-first) in a different dir, so the slice scanner never sees them. `label_in_use_on_disk` (`cli.py:2159`) gains a check so a label already owning an effort doc is also refused. A filesystem scan of `sessions/efforts/` exists only as a **fail-loud integrity check** (duplicate / missing numbers), not as the allocator.
- **Frontmatter is minimal** — `created` + `edited_by`, nothing else (resolved decision). `status`, the branch map, and `number` are registry-only; the label is in the filename.
- **Phases / pivots are flat + linked.** More numbered efforts, with `Parent:` / `Supersedes:` links *in the body* (not nested folders, the same way plans link to brainstorming). Amend in place; git keeps the history.
- **Template:** a new `templates/skills/effort-template.md`, lean — a one-paragraph framing, then `## Shape of the solution`, `## Constraints & appetite`, `## Non-goals / deferred`, `## Open questions`, `## Phasing & related efforts` (with `Parent:`/`Supersedes:` hints). Scaffold comment states that branch/base, `open`/`closed`, and `number` live in `efforts.json`, not here, and to re-run `zentaizo edited <doc>` after edits.

## `main` is the deliverable trunk

Special by **role**, not by content: the effort that already exists at bootstrap, that work flows into until you branch, and that is never `close`d — exactly how git `main` is special. It may record editable repos it touches without a feature branch (`branch: null` until a divergence opens one), so `_main_effort()`'s `repos: {}` becomes "no repos *yet*," not "no repos ever." Under the uniform rule, `main` gets `0001-main.md` at workspace creation.

"Never `close`d" is **enforced, not just documented**: `effort close main` (`cli.py:2472`) refuses. And because `main` never goes through `effort new --repo`, **attaching a repo to it** relies on a small relaxation of `set-branch` (below): `set-branch main --repo NAME` (bare, no `=BRANCH`) records `{branch: null, base: null}` — *the repo is part of the effort; no divergence branch has been recorded yet* — and `set-branch main --repo NAME=BRANCH` upgrades it when a real branch opens (the DC→MC moment).

## Command surface

- **`effort new <label>` (extended, `cli.py:2365`)** — unchanged label resolution (explicit word or themed suggestion) and `--repo`/`--describe` handling, then: allocate the registry `number`, scaffold the doc from `effort-template.md`, write it with `_write_exclusive`, stamp the first `edited_by` via `_record_edited_by(resolve_editor_identity(...))` (identical to `_next_slice`, `cli.py:2769`), store the allocated `"number"` on the registry entry, and print the doc path. `--describe` sets the registry `description` (the **canonical** short form); it *also* seeds the doc's opening framing line as **initial scaffold text only** — the human expands that line into the full plan, and it is not kept in sync with the registry `description` afterward.
- **`effort show` (`cli.py:2423`)** — also prints the resolved doc path (from `number` + `label`) alongside the repos/branches/slices.
- **`effort close` (`cli.py:2472`)** — refuses `main` (the trunk is uncloseable); every other effort closes as today.
- **`effort set-branch` (`cli.py:2449`), relaxed** — `--repo NAME=BRANCH` works as today (computes `base`); `--repo NAME` (bare) is newly legal and records `{branch: null, base: null}` — *the repo is part of the effort; no divergence branch has been recorded yet* — symmetric with `effort new --repo NAME` (which already produces that shape via `_repo_entry`, `cli.py:2325`). This is how an effort — `main` especially — attaches a repo it touches without a feature branch. **No silent downgrade:** if the repo already has a recorded branch, bare `--repo NAME` *refuses* (`"repo already has a branch; pass NAME=BRANCH to update"`) rather than erasing `{branch, base}` — consistent with the fail-loud principle.
- **`zentaizo validate` (`cli.py:3145`), extended** — beyond atlas validation, runs the effort-doc **integrity scan** (orphan docs with no registry entry, duplicate `number`s, registry efforts whose doc is missing, legacy efforts lacking `number`). This is the discovery surface for those anomalies; it reports, it never auto-fixes.
- **`zentaizo path effort [label]`** (new, read-only; added to `_add_path_parser`, `cli.py:3351`) — resolves the effort's doc path from the registry `number` + `label`, paralleling `path slice`/`path active`, so agents can locate it deterministically.
- **No `next-effort`** (see principle 7).

## Scaffolding: CLI vs. agent

The CLI fills `created` (quoted UTC), stamps the first `edited_by` entry, allocates the `number`, and seeds the opening framing line from `--describe` as **initial scaffold text** (not a maintained mirror of the registry `description`). The agent/human fills the prose body and, for pivots, the `Parent:`/`Supersedes:` links. Mirrors the `plan-template.md` split (`cli.py:2634`).

## Migration (`upgrade-zentaizo`)

This is an in-workspace, AI-driven migration, not a CLI command — consistent with how `next-slice-cli-helper.md` deferred existing-workspace migration to the skill. `templates/global-skills/zentaizo/upgrade-zentaizo.md` gains a step: for an existing workspace, assign each registry effort a `"number"` (`main` = 1; others by `created` order) and backfill `sessions/efforts/NNNN-<label>.md`, seeding each doc's framing from the effort's existing `description`. Targets `zen-segmend-mesher` and the nascent `zen-ACG`. `SKILL.md`'s verb list is updated to note `effort new` now scaffolds a doc and that `path effort` exists.

## Integrity & migration failure modes

The registry owns `number`; the filesystem is checked against it, never trusted to allocate. Each anomaly **fails loud** rather than silently synthesizing:

- **Registry effort with no doc** — `path effort` / `effort show` for that effort error with a pointer to `upgrade-zentaizo`; they never fabricate a doc.
- **Doc with no registry entry (orphan)** — surfaced by `zentaizo validate` (the concrete discovery surface); reconciliation is then the upgrade skill's job, not an auto-register.
- **Two docs sharing a number** — corruption; reported by `zentaizo validate`.
- **Legacy registry lacking `number`** (pre-this-design) — `effort new` refuses (it cannot safely allocate the next number) and points to `upgrade-zentaizo`; read commands (`effort list` / `show`) degrade gracefully, marking such efforts `(needs upgrade)` rather than crashing.

Targeted checks live on the specific CLI operation (fail loud on the file you asked for); the broad **detection** of orphans / duplicate numbers / missing `number` is `zentaizo validate`; and the broad **reconcile** — backfilling docs, assigning numbers, renaming — is the AI-driven `upgrade-zentaizo` pass, consistent with how `next-slice-cli-helper.md` deferred existing-workspace migration to the skill.

## Instruction touchpoints that must change

(Mirroring the inventory style of `next-slice-cli-helper.md:279`.)

- **`workspace_agents()` (`cli.py:272`):** § Active Efforts (efforts now have a plan doc; `main` = trunk; `effort close main` is refused); add `efforts/` to the § Recording Work table, the § Filename Convention table, and the `edited_by` frontmatter-bearing set; retarget § From Brainstorming → effort doc → slices.
- **`workspace_readme()` (`cli.py:164`):** layout tree gains `sessions/efforts/`; workflow step 5 notes the effort *is* its plan doc.
- **`plan-and-implement.md`:** pre-flight + drafting reference the effort doc as the plan-of-record above slices; `effort new` scaffolds it; fix the `main` sentence (`:27`).
- **`plan-template.md`:** one-line comment touch (the effort itself now has a doc).
- **`docs/workspace-format.md`:** layout + the frontmatter-bearing set. **`docs/cli.md`:** it currently stops after `edited` (`docs/cli.md:115`) and never documents the `effort` / `path` / `next-*` surface at all — bring that whole surface in (not just the new `effort new` doc behavior + `path effort`).
- **`global-skills/zentaizo/SKILL.md` + `upgrade-zentaizo.md`:** as above.

## Edge cases and non-goals

- **Brainstorming is untouched.** It stays freeform dated dumps (`YYYY-MM-DD-<slug>.md`, participants listed inline, no frontmatter) — the raw input an effort doc distills *from*. The effort doc is the *curated* sibling; the dumps remain the only frontmatter-free, schema-free session type.
- **Not a rename of `next-*`.** A unifying `new` namespace (`zentaizo new change|effort|…`) was considered and rejected: pure churn that doesn't reduce concept count (`effort` still needs its management namespace).
- **The Claude-Remote session-titles work** (`docs/changes/2026-06-07-session-title-from-slice.md`) is a **separate, later** effort, sequenced after this lands.
- **Historical design docs left as dated artifacts**, not rewritten to current behavior — including the stale `main` snippet in `docs/changes/2026-05-27-next-slice-cli-helper.md`.

## Testing

Existing effort/session tests cover registry allocation and path behavior (`tests/test_cli.py:1045`, `tests/test_cli.py:1168`); extend, don't duplicate.

- Update the `create` test: workspace now has `sessions/efforts/` and `0001-main.md`; assert the corrected `main` description.
- New `EffortDocTests`:
  - `effort new` writes the doc and stamps `created` + `edited_by`; the registry-owned `number` increments independently of the per-effort slice counter.
  - `path effort` resolves the doc (derived from registry `number` + label); `effort show` prints the doc path.
  - `effort close main` is refused; every other effort still closes.
  - a label already owning an effort doc is refused (collision).
  - `set-branch main --repo NAME` (bare) records `{branch: null, base: null}`; `--repo NAME=BRANCH` upgrades it.
  - **missing-doc / mismatch:** a registry effort whose doc is absent fails loud on `path effort` / `effort show`; a legacy registry without `number` makes `effort new` refuse with the `upgrade-zentaizo` pointer.
  - **no downgrade:** bare `set-branch` on a repo that already has a recorded branch refuses (doesn't erase `{branch, base}`).
  - **`zentaizo validate`** flags an orphan effort doc and a duplicate `number`.
- Update any assertion checking the old `main` description string.
- Focused run first (`pytest -k "effort or create"`), then full `pixi run -q python -m pytest`, then `ruff`.

## Build order

1. CLI core (A): constants/seeding (+ `number` on `_main_effort`), registry-based number allocation, `scaffold_effort`, extend `effort_new`, `create_workspace`, `effort_show`, `effort_close` (main refusal), `set-branch` relaxation (with no-downgrade), `path effort`, `label_in_use_on_disk`, and the `zentaizo validate` effort-doc integrity scan.
2. `effort-template.md` (B).
3. Generated instructions + skills + docs (C–E), as one prose sweep (incl. the `docs/cli.md` surface gap).
4. Tests (F); validate.

Lands as a single commit to `main` (trunk-based); the prepare-commit-msg hook supplies the attribution trailer.

## Related

- [`next-slice-cli-helper.md`](2026-05-27-next-slice-cli-helper.md) — the effort registry / `next-*` / `path` design this extends.
- [`zen-segmend-mesher-template-integration-round-2.md`](2026-05-27-zen-segmend-mesher-template-integration-round-2.md) — the dogfooding workspace whose `main`-usage history motivated the charter correction.
- [`2026-06-07-session-title-from-slice.md`](2026-06-07-session-title-from-slice.md) — the separate, follow-on Claude-session work.
