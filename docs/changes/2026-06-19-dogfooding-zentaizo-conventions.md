---
created: 2026-06-19
status: accepted
accepted: 2026-06-20  # Codex sign-off (round 2)
edited_by:
  - 2026-06-19  Claude Opus 4.8 (1M context)
  - 2026-06-19  Codex (review), Claude Opus 4.8 (1M context, revision)
  - 2026-06-19  Bill Katz, Claude Opus 4.8 (1M context, option-a rewrite)
  - 2026-06-20  Codex (review), Claude Opus 4.8 (1M context, revision)
  - 2026-06-20  Bill Katz, Claude Opus 4.8 (1M context, editorial-framing reframe)
  - 2026-06-21  Bill Katz, Claude Opus 4.8 (1M context, "self-hosting"→dogfooding rename)
  - 2026-06-21  Codex (review round 3), Claude Opus 4.8 (1M context, operational fixes)
---

# Dogfooding zentaizo: a workspace of record + distilled editable-repo design docs

_Design doc. Promotes
[`../brainstorming/2026-06-18-dogfooding-zentaizo-conventions.md`](../brainstorming/2026-06-18-dogfooding-zentaizo-conventions.md).
Records the maintainer's decisions: develop zentaizo inside a zen workspace;
vendor zentaizo as a plain `edit` clone (topology option a); promote distilled,
repo-scoped design docs into the editable repo. **Reframed 2026-06-20** from a
confidentiality model to **editorial distillation** (see the reframing note).
Codex round-2 (2026-06-20) signed off on the topology. **Status: accepted —
ready to implement pending maintainer go.**_

## Reframing note (2026-06-20): editorial distillation, not confidentiality

Earlier drafts framed this around **confidentiality** ("E-strict," irreversible
public history, a confidentiality checklist gate). That **oversells the intent**
and is superseded. The driver is **editorial: signal, digestibility, and
professionalism.** A zen workspace keeps the full, low-level, often
conversational provenance; the editable repo receives a **distillation** of the
architecture and design motivations, written to read cleanly. Generalizing
"who said what, when" into author-level decisions, and not persisting
conversations verbatim, is about removing *noise* and reading professionally —
**not** a security control. (A workspace may be kept private for ordinary project
reasons; that is independent of this design.) The promotion mechanism is the
**user-initiated distillation skill** in
[`../brainstorming/2026-06-20-distillation-skill.md`](../brainstorming/2026-06-20-distillation-skill.md).
For zentaizo specifically the workspace can be **public** — nothing in its trail
is sensitive; the value is purely focus and readability.

## Codex review resolution (topology — still valid after the reframe)

Round 1 (2026-06-19):

| # | Sev | Finding | Resolved by |
|---|---|---|---|
| 1 | High | Private-workspace topology unsupported (`repos/<name>` is a clone-from-URL; sandbox rejects out-of-tree paths) | **Vendor zentaizo as a plain `edit` clone (option a)** — the designed mechanism, zero new CLI features. The brainstorm's `→ ~/work/zentaizo` *link* was unsupported and unnecessary. |
| 2 | High | `AGENTS.md` rewrite must keep the negative rule | Keep "no atlas/`sessions/`/`summaries/` in this repo" — those are *workspace* artifacts, kept at the workspace root, not in the editable repo. |
| 3 | Med | "installed zentaizo" not enforceable under editable/Pixi installs | Stable-runner preflight (below). |
| 4 | Med | Promotion mechanism underspecified | Now the user-initiated **distillation skill** (own brainstorming doc). |
| 5 | Low | First artifacts come from already-public docs | Existing public docs are fine (nothing sensitive); they **migrate** to the workspace and are replaced by distilled docs — see Migration. |

Round 2 (2026-06-20):

| # | Sev | Finding | Resolved by |
|---|---|---|---|
| 1 | Med | Preflight checks ambient `python`, not the interpreter behind `zentaizo` | One **stable runner** `STABLE_PY`; run **both** preflight and bookkeeping through it. |
| 2 | Med | CLI doesn't discover a parent workspace from inside `repos/zentaizo` | **Working-location rule:** run from the workspace root or with `-C ~/work/zen-zentaizo`. |
| 3 | Low/Med | Convergence asserted yet also listed open | Made **decided + a blocking migration criterion**. |

Verdict: Codex found the option-(a) topology **sound** and confirmed the live code
supports it (gitignored `repos/`, edit-repo clone under `repos/<name>`, sandbox
treats edit repos as writable).

Round 3 (2026-06-21) — implementation-readiness pass on this doc and the Pass-1 plan:

| # | Sev | Finding | Resolved by |
|---|---|---|---|
| 1 | Med | Bootstrapping `-C` rule is wrong for several commands — `edited` takes a session-file path, `commit-trailer` takes no workspace arg, and `validate`/`status`/`fetch` take a **positional** workspace, not `-C` | **Split the rule by command family** (Bootstrapping), verified against `build_parser` (`cli.py:4552-4660`, `cli.py:4828`). |
| 2 | Med | Ongoing distillation treated as accepted, but the distillation skill is an unbuilt brainstorm | **Scoped this doc** to foundation + one-time manual bootstrap; ongoing distillation deferred until the skill is designed (Implementation scope). |
| 3 | Med | Docs migration lacks a concrete file-by-file mapping | Added a **map-first** step and a `validate`-after gate (Sequence 2–3). |
| 4 | Low/Med | `AGENTS.md` rewrite scope too narrow (named only `:11-15`) | Broadened to **all** design-workflow references (acceptance criteria). |

Codex verdict: topology + editorial reframe sound; remaining risks operational, not
conceptual — addressed above.

## Decision

Develop zentaizo inside a zen workspace, `zen-zentaizo` — dogfooding the tool on
its own repo. **Topology option (a):**
vendor zentaizo the normal way every editable repo is vendored — a plain `edit`
clone — and make that clone the **single canonical checkout** for zentaizo
development. The workspace root keeps the full provenance; **distilled,
repo-scoped design docs are promoted into the editable repo** by the
user-initiated distillation skill. This gives zentaizo's own work the full
effort / slice / sandbox machinery with **zero new CLI features**.

## Topology: vendor zentaizo as a plain `edit` clone

The brainstorm imagined `repos/zentaizo` as a *link* to the existing working tree.
That is **unsupported** (a repo source requires `name`/`url`/`ref`,
`cli.py:1059-1061`; `fetch_edit_repo` **clones from `url`** into `repos/<name>`,
`cli.py:1387-1394`; sandbox path-hardening rejects out-of-tree names,
`_safe_repo_relpath`, `cli.py:4371-4378`) and **unnecessary**: a plain `edit`
clone is the designed mechanism. The clone has its **own `.git` → zentaizo's
public remote**, and `repos/` is **gitignored by the workspace** (`cli.py:876`),
so code commits push to the public remote exactly as today.

Adopt the workspace's `repos/zentaizo` as the one canonical checkout and converge
the standalone `~/work/zentaizo` (migration checklist below). A local-path atlas
source (Codex option c) would only preserve the *existing path* — a convenience
deferred to a separate CLI proposal, not needed here.

## One tree, two git repos

`~/work/zen-zentaizo/` holds **two independent git repositories**, separated by
`.gitignore`:

- **Workspace root — the provenance home.** Its own git repo tracking the full
  `sessions/` trail (efforts, brainstorming, changes, debugging, questions,
  handoffs, reports), `zentaizo.atlas.json`, and `summaries/`. The atlas lists
  **zentaizo as the one `edit` source** and the borrow-from tools (Context Hub,
  Graphify, coding-harness docs) as `reference`. (Public for zentaizo; private
  only if a project needs it.)
- **`repos/zentaizo` — the editable repo.** A normal `edit` clone, gitignored by
  the workspace, with its own `.git` → zentaizo's public remote. Its published
  docs are the **reference docs** (`docs/cli.md`, `docs/workspace-format.md`,
  `docs/use-cases.md`) plus **distilled design docs**; it **never** grows
  `zentaizo.atlas.json`, a `sessions/` tree, or `summaries/`.

The `.gitignore` boundary cleanly separates **full provenance (workspace root)**
from **distilled output + reference docs (editable repo)**.

## Distillation (the promotion mechanism)

Promotion is the **user-initiated distillation skill** — full design in
[`../brainstorming/2026-06-20-distillation-skill.md`](../brainstorming/2026-06-20-distillation-skill.md).
In brief: a skilled agent, run on request, reads the workspace's settled
decisions and proposes/updates **repo-scoped, distilled** design docs in the
editable repo, generalizing personal specifics to author-level decisions and
never copying conversations verbatim. A human reviews and approves; the skill
reconciles rather than paves prior human edits (an `upgrade-zentaizo`-style
3-way merge). Two principles for what lands in the editable repo: **(1)
repo-scoped**, **(2) distilled architecture + rationale, generalized.**

**Implementation scope (this doc).** Foundation (stand up workspace + vendor) and
the **one-time manual bootstrap** below are in scope. *Ongoing* distillation relies
on the distillation skill, which is still a brainstorm (`status: brainstorming`,
open questions, no template in `src/zentaizo/templates/skills/`). Designing/building
that skill is **deferred and gated separately**; until then the distilled
`docs/design/` is produced by a manual / ad-hoc agent pass, not by a skill.

## Migrating zentaizo's existing `docs/` into the workspace

This is how today's repo becomes `zen-zentaizo` and what happens to `docs/`.

**Not all of `docs/` is noise — separate two kinds:**

- **Reference docs → stay in the editable repo.** `docs/cli.md`,
  `docs/workspace-format.md`, `docs/use-cases.md` are already-distilled,
  contributor-facing reference. They remain in `repos/zentaizo`.
- **Provenance → moves to the workspace.** `docs/brainstorming/` and
  `docs/changes/` are the noisy before/after trail — the same kind a zen
  workspace keeps in `sessions/`. They move to the workspace root's
  `sessions/brainstorming/` and `sessions/changes/`.

**The editable repo gains distilled design docs** (e.g. under `docs/design/`)
capturing the current architecture + rationale, in place of the migrated
provenance.

**Sequence:**

1. Stand up the workspace and vendor zentaizo (convergence of the standalone
   checkout is a separate, later step).
2. **Build the migration map first.** `sessions/` is not a drop target: `changes/`
   files are effort-scoped, CLI-allocated slice plans (`<label>-NNNN-<slug>.md`)
   with specific frontmatter, so the existing dated design docs do **not** map 1:1.
   Inventory every file in `docs/brainstorming/` + `docs/changes/` recording, per
   file: target (freeform `brainstorming` vs. a `changes` slice), the effort/label
   and `status` it gets, the CLI-allocated id + new name, and the cross-links to
   rewrite. (Decided migration style: **full effort-scoped re-allocation**.)
3. Execute the map: allocate ids via the CLI (`next-change` / `next-brainstorming`),
   move + rename, rewrite frontmatter and every cross-link — then
   **`zentaizo validate ~/work/zen-zentaizo` must pass.**
4. Produce the first distilled design docs in `repos/zentaizo/docs/design/`
   (manual pass — see Implementation scope).
5. `git rm` the migrated `docs/brainstorming/` + `docs/changes/` from
   `repos/zentaizo` HEAD (keep the reference docs); commit to the public remote.

**Two caveats:**

- **One-off, not the distillation skill.** zentaizo has **never been under a zen
  workspace**, so relocating its pre-existing `docs/` is a **one-time manual
  reorganization** — distinct from the distillation skill, which models the
  ongoing, typical case (editable repos that live under a workspace). Producing
  the initial distilled `docs/design/` is a manual / ad-hoc agent pass; the skill
  is not designed around this bootstrap.
- **History is retained, not scrubbed.** Removing the provenance from HEAD does
  not erase it from git history — and that is fine; nothing is sensitive. This is
  tidying the tree, not a scrub. Provenance accrues in the workspace going forward.

## Bootstrapping & working-location rules

Under option (a) the hazard is co-located: the code under development **is**
`~/work/zen-zentaizo/repos/zentaizo`, inside the very workspace whose root
`sessions/`/`efforts.json` the CLI also mutates. The dev flow uses an editable
install (`README.md:83`, `docs/cli.md:27`), so a default `zentaizo`/`python` may
resolve to that clone.

- **Define one stable runner.** Pin a non-editable install (`pipx`, or a venv with
  `pip install .` — *not* `-e`); call its interpreter `STABLE_PY`. Run **both**
  preflight and bookkeeping through it.
- **Preflight:** `STABLE_PY -c "import zentaizo; print(zentaizo.__file__)"` must
  resolve **outside** the workspace's `repos/zentaizo`; else abort.
- **Bookkeeping — point each command at the workspace explicitly** (the CLI never
  discovers a parent workspace from inside `repos/zentaizo`: `find_atlas` checks only
  the given path, `cli.py:928-937`). The argument form **differs by command family**,
  so this is *not* one uniform `-C` flag (verified against `build_parser`):
  - `-C/--workspace` flag (`_add_workspace_arg`, `cli.py:4828`): `effort *`,
    `next-*`, `path *` — e.g. `STABLE_PY -m zentaizo next-change <slug> -C ~/work/zen-zentaizo`.
  - **positional** workspace dir (`nargs="?"`, default `.`): `validate`, `status`,
    `fetch`, `summarize`, … — e.g. `STABLE_PY -m zentaizo validate ~/work/zen-zentaizo`.
  - `edited <session-file>`: a positional path to the **session file**, not a
    workspace dir (`cli.py:4630`).
  - `commit-trailer` / `cache-trailer`: **no** workspace argument — run in the
    editable repo's own git context (`cli.py:4608-4623`).
- **Exercise the dev build only in `/tmp`** (`pixi run zentaizo` against throwaway
  workspaces), never against `zen-zentaizo`.

## Acceptance criteria

- [ ] **`AGENTS.md` rewritten — every design-workflow reference, not one block.**
  (1) the "not a workspace" stance (keep the negative rule: no
  atlas/`sessions/`/`summaries/` in this repo — workspace artifacts live at the
  workspace root), adding the two-repo model, the distillation mechanism, and the
  bootstrapping rule; (2) the `docs/` layout description that names
  `docs/changes/` + `docs/brainstorming/` as the repo's design locations; (3) the
  "start a non-trivial change as a dated design doc in `docs/changes/`" rule. After
  migration those locations move to the workspace `sessions/` trail, so all three
  must be rewritten or agents keep using the old public-doc workflow.
- [ ] The bootstrapping preflight passes via the stable runner, and
  session/bookkeeping commands point at the workspace via each command's own
  workspace argument (per the command-family rule in Bootstrapping).
- [ ] **Checkout convergence migration (blocking).** Before retiring
  `~/work/zentaizo`: its tree is clean (or changes intentionally carried); all
  remotes/branches exist in the new `repos/zentaizo` clone; only then is the old
  checkout retired or made read-only, kept as a temporary backup.
- [ ] **Docs migration (blocking).** `docs/brainstorming/` + `docs/changes/`
  moved to the workspace `sessions/` trail; reference docs retained; distilled
  `docs/design/` produced; provenance `git rm`-ed from the editable repo HEAD.
- [ ] zentaizo's repo content contains **no** `zentaizo.atlas.json`, `sessions/`,
  or `summaries/`; `repos/` is gitignored so the two histories never cross.

## Distillation invariants

- The workspace holds full provenance; the editable repo holds the distillate +
  reference docs; the `.gitignore` boundary keeps them in separate histories.
- The **negative record** (ideas considered and not implemented) is **condensed**
  when distilled — it is the most useful design context for a future contributor,
  but as a digest, not verbatim churn.
- Distillation generalizes personal/conversational specifics to author-level
  decisions for readability and professionalism — an editorial step, not a
  security filter.

## Residual decision (resolved 2026-06-20)

Open-Q6 — "is any of zentaizo's design trail confidential?" — is **answered: no.**
That removed the confidentiality rationale and drove the editorial reframe above.
The workspace/editable-repo split is retained for **signal and readability**, not
secrecy; for zentaizo the workspace is public.

## Related

- [`../brainstorming/2026-06-20-distillation-skill.md`](../brainstorming/2026-06-20-distillation-skill.md)
  — the distillation skill that is this design's promotion mechanism.
- [`../brainstorming/2026-06-18-dogfooding-zentaizo-conventions.md`](../brainstorming/2026-06-18-dogfooding-zentaizo-conventions.md)
  — the brainstorm this promotes (Options A–E); option (a) realizes Option E's
  topology, reframed from confidentiality to editorial distillation.
- [`../brainstorming/2026-05-26-ideas-worth-borrowing.md`](../brainstorming/2026-05-26-ideas-worth-borrowing.md)
  — idea #5 (workspace → shareable export) is the same "publish distilled
  knowledge" instinct.
- `AGENTS.md:11-15` — the "not a workspace" stance the rewrite replaces (keeping
  its negative rule, scoped to "this repo's tracked content").
- `docs/workspace-format.md`, `workspace_agents()` (`cli.py:285`) — the
  conventions the workspace instantiates.
- CLI facts: `cli.py:1059-1061` (repo requires `name`/`url`/`ref`),
  `cli.py:1387-1394` (clones from URL), `cli.py:876` (`repos/` gitignored),
  `cli.py:4371-4378` (out-of-tree rejected), `cli.py:928-937` / `cli.py:4832`
  (no parent-workspace discovery; `-C` defaults to `.`).
