# Foundations: Source Roles, Curation, and Templates

_Distilled design doc — current architecture + rationale._

## What it is

The foundations subsystem is the layer that decides *what* a Zentaizo workspace knows and *how much an agent may touch it*. It rests on three settled ideas. First, every repo in a workspace carries a **role** — `edit` or `reference` — that drives fetch behavior and, downstream, sandbox access. Second, intent and resolved state are split into two files: the human-authored **atlas** (`zentaizo.atlas.json`) versus the machine-resolved **lock** (`zentaizo.lock.json`), with a bundled `curate-atlas` skill that walks an AI through populating the atlas. Third, the conventions a real workspace evolves — directory layout, filename rules, frontmatter, commit hygiene — are fed back into Zentaizo's own **templates** so the next `zentaizo create` ships them.

Together these turn a directory of cloned repos into one coordinated workspace, the way a monorepo holds related code: editable repos the agent branches and commits against, reference repos it reads but never rewrites, and a curated atlas of sources that is version-controlled intent rather than incidental disk state.

## Architecture

### Roles drive fetch and lock semantics

A repo entry in the atlas carries an optional `role` field. The accepted values and default are defined once (`src/zentaizo/cli.py`: `VALID_ROLES = ("edit", "reference")`, `DEFAULT_ROLE = "reference"`), and `repo_role()` normalizes any entry — including a missing or unrecognized `role` — to a known value, so reference is the safe default everywhere. `validate_workspace()` accepts a present `role` only if it is in `VALID_ROLES` and otherwise reports a clear error.

`fetch_workspace()` branches per repo:

- **`fetch_reference_repo()`** treats `ref` as a pin. It re-resolves on every run (`git fetch --tags --prune`, then `git checkout <ref>`), so `ref: main` tracks main while a tag or SHA stays put. A dirty working tree aborts the fetch with a message offering `git -C <path> checkout .` or a role change — dirty here means accidental edits, not work in progress. The locked entry records `role: "reference"`, the resolved `commit`, and `dirty: false`.
- **`fetch_edit_repo()`** treats `ref` as a *starting point*. On first clone it checks out `ref`; on every subsequent fetch it refreshes remotes (`git fetch --tags --prune`) but never touches HEAD or the working tree, so branches and in-progress commits survive. It computes whether HEAD is clean and behind the freshly resolved upstream; if so it **prints** the exact rebase command. `zentaizo fetch --rebase` actually runs the rebase for every clean-and-behind edit repo — never automatically, fitting headless use. The locked entry records `role: "edit"`, `commit` set to the *upstream* resolution (the canonical version), and a separate `head` for where the user actually is, plus the real `dirty` flag.

This is the key lock asymmetry: for an edit repo the lock answers "what does the atlas `ref` resolve to right now?" while `head` answers "where is the user?" — making divergence visible rather than erasing it. `status_workspace()` reads this back, grouping output into edit vs reference repos and surfacing drift (an edit repo behind upstream gets the rebase hint; a reference repo whose HEAD differs from its locked SHA is flagged as drift). `print_counts()` reports `N repos (X edit, Y reference)`.

`fetch_edit_repo()` also installs the bundled commit-attribution hook into each editable clone (`install_commit_attribution_hook()`), so commits in vendored edit repos are attributed even though the repo was not created by `zentaizo create`.

### Atlas (intent) vs lock (resolved state)

The atlas is hand-authored and declarative: sources, why they matter, and each repo's `role` and `ref`. A freshly created workspace deliberately ships *without* an atlas — its absence is the first-task prompt (`missing_atlas_message()`, surfaced by `workspace_agents()`). `default_atlas()` exists only as the reference seed shape and shows both roles. The lock is machine-written only, never by hand, and records resolution: resolved commit, local path, dirty status, fetch time (and the `head`/`commit` split for edit repos). Six commands write it — `create` (the initial seed plus the conventions stamp), `fetch`, `fetch-docs`, `graph`, the graph auto-refresh inside `fetch`, and `upgraded` — each through `write_json(… LOCK_NAME …)` in `cli.py`. The boundary is documented in `docs/workspace-format.md` and enforced by convention — the CLI never hand-writes the atlas, and the lock is never authored by a human.

Curation is delegated to a model-agnostic procedure, `src/zentaizo/templates/skills/curate-atlas.md`, copied into every workspace's `skills/` by `install_skills_into_workspace()` during `create_workspace()` (suppressed by `--no-skills`). It is plain markdown with no YAML frontmatter and no tool-specific directory, so any LLM coding tool can follow it; discovery flows through the generated `AGENTS.md`, which `workspace_agents()` emits with an explicit boundary: the atlas describes the *system*, while user preferences and coding style belong in the harness's own memory/rules files. The skill interviews one question at a time, has an explicit Step 2.5 ("Edit or reference?") and a `ref`-strategy step keyed to role, and always previews a unified diff before saving — never silently rewriting the user's atlas.

The config-file naming reflects this split deliberately: `ATLAS_NAME = "zentaizo.atlas.json"` pairs with `LOCK_NAME = "zentaizo.lock.json"`. `find_atlas()` still reads a legacy `zentaizo.config.json` (`LEGACY_CONFIG_NAME`) for backward compatibility, but the rename was a hard, pre-1.0 cut with no alias on the write path.

### Roles also drive the sandbox policy

The role split is not only a fetch concern; it *is* an access policy. `compute_policy()` (`src/zentaizo/cli.py`) is a pure function over the atlas that derives a least-privilege policy: editable repos and the always-writable workspace dirs (`sessions/`, `summaries/`, `tmp/`, the graph output) are `writable`; reference repos are `readonly`. A `mode` parameter (`implement` vs `curate`) decides whether the workspace's own owned files (atlas, lock, `skills/`, `AGENTS.md`, etc.) are read-only (an implementing agent) or writable (a curation agent). `zentaizo sandbox` exposes this: `--target policy` prints the JSON policy with no side effects (the default), and `--target claude` renders managed deny rules into `.claude/settings.json`, with `--check` reporting drift without writing. Repo names are path-hardened (`_safe_repo_relpath()`) before becoming grant/deny paths.

### Workspace conventions feed back into templates

The text a workspace ships with lives here as code and template files, not as documentation a workspace re-derives. `workspace_agents()` and `workspace_readme()` in `cli.py` generate `AGENTS.md` and `README.md`; the `skills/` templates (`curate-atlas.md`, `plan-and-implement.md`, `plan-template.md`, `effort-template.md`, `report-template.md`, `handoff-template.md`, `brainstorming-template.md`) are copied verbatim. When a live workspace evolves a convention that proves out — a new `sessions/` subdirectory, a filename pattern, a frontmatter field, commit-separation hygiene — that convention is promoted back into these generators and templates, with workspace-specific examples generalized. Changing a workspace convention is therefore a code change in this repo.

There is intentionally no `zentaizo update` command. A whole-file overwrite cannot preserve a workspace's local customizations, cannot migrate the session files already on disk (renames, frontmatter rewrites, cross-reference fixes) when a convention changes, and cannot distinguish "adopt the new convention" from "this workspace deliberately diverged." Upgrades are instead an AI-driven procedure, `upgrade-zentaizo.md`, bundled in the global skill (`templates/global-skills/zentaizo/`, installed via `zentaizo skills install`) and explicitly experimental — opt-in, not auto-installed into new workspaces. Convention authority lives in the *workspace's* `AGENTS.md` (version-pinned in its git history, read by every harness regardless of which global skill is installed), not in the per-user global skill, which stays narrow: what Zentaizo is, the atlas's purpose, memory-system boundaries, and where to look.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Per-repo role field | `role: "edit"` \| `"reference"`, default `reference` | Editing is opt-in; the safe default protects working trees and is backward compatible with role-less atlases. |
| Reference fetch semantics | Always re-resolve the pin; refuse a dirty tree | `ref: main` should track main; reproducibility comes from pinning a SHA/tag, not from freezing the fetch. Dirty = accidental edit. |
| Edit fetch semantics | Clone once, then never touch HEAD/working tree; print rebase, run it only with `--rebase` | The whole point of an edit repo is divergence; fetch must not clobber in-progress work, and headless use rules out interactive prompts. |
| Edit-repo lock shape | Lock `commit` = upstream resolution; separate `head` = user's HEAD | Keeps lock semantics consistent across roles and makes drift visible instead of hidden. |
| Intent vs resolved state | Two files: human-authored atlas, machine-authored lock | One file you hand-edit; the rest is generated and re-derivable. The atlas declares a `ref`; the lock records what it resolved to. |
| Config filename | `zentaizo.atlas.json` (pairs with `zentaizo.lock.json`) | "Atlas" names the curated-knowledge intent; symmetry with the lock. Hard pre-1.0 rename, legacy name still readable. |
| Curation surface | Bundled `curate-atlas.md` skill, plain markdown, discovered via `AGENTS.md` | Model-agnostic; no tool-specific directory; keeps the atlas (system) boundary clean from host memory (user). |
| Role enforcement layering | Schema (intent) + CLI (soft) + sandbox policy (hard) | Each layer reads the same `role`; the atlas split *is* the sandbox access policy via `compute_policy()`. |
| Convention home | Workspace `AGENTS.md` + bundled templates, not the global skill | `AGENTS.md` is version-pinned per workspace and read by every harness; conventions belong to the workspace, not the user's PATH. |
| Workspace upgrades | AI-driven `upgrade-zentaizo` skill, no `zentaizo update` command | A blind overwrite cannot migrate downstream artifacts or preserve local divergence; that reconciliation needs judgment. |

## Considered and not taken

- **Filesystem `chmod` lockdown for reference repos** — rejected; it breaks `git checkout`, `git gc`, and other internals. Real read-only enforcement belongs in the sandbox/container layer, now realized as `compute_policy()` + `zentaizo sandbox`.
- **Auto-creating a working branch on first clone of an edit repo** — declined; Zentaizo stays neutral about branch naming and lets the user/agent pick their convention.
- **A `zentaizo update` whole-file template overwrite** — removed in favor of the AI-driven `upgrade-zentaizo` procedure, for the migration/preservation/judgment reasons above.
- **Backward-compatible alias for the old `zentaizo.config.json` name on write** — not taken; pre-1.0 with no shipped users justified a hard rename. The legacy name remains *readable* only.
- **A multi-format `emit-mounts` command** (`--format compose|devcontainer|podman|paths`) — the original sketch for projecting roles into a sandbox. Superseded by `zentaizo sandbox`, which renders the atlas-derived policy into a harness's *native* guardrails (e.g. Claude deny rules) rather than emitting generic mount fragments.
- **Putting workspace conventions in the per-user global skill** — rejected; conventions can legitimately differ per workspace and must travel with the workspace's git history, so they live in the generated `AGENTS.md` and bundled templates.

## See also

- `src/zentaizo/cli.py` — `repo_role()`, `fetch_reference_repo()`, `fetch_edit_repo()`, `fetch_workspace()`, `status_workspace()`, `validate_workspace()`, `default_atlas()`, `compute_policy()`, `sandbox_command()`, `workspace_agents()`, `workspace_readme()`.
- `src/zentaizo/templates/skills/curate-atlas.md` — the curation procedure.
- `src/zentaizo/templates/global-skills/zentaizo/upgrade-zentaizo.md` — the AI-driven upgrade procedure.
- `docs/workspace-format.md` — atlas/lock/role schema and the workspace layout.
- `docs/cli.md` — `create`, `validate`, `status`, `fetch`, `sandbox` command reference.
- `README.md` — the edit/reference and atlas-vs-lock framing in "Core Ideas".
