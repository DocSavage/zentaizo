# Changelog

All notable changes to this project are documented here.

This project uses the Keep a Changelog format. Versions 0.8.0 and earlier predate this changelog.

## [0.16.0] - 2026-08-22

One release entry for the whole landing since 0.15.2, per the collapse rule:
six slices' worth of trunk work shipped without a version, and MINOR is the
highest increment among them. **Conventions generation: 6.**

### Added

- `zentaizo bring-up` runs the mechanical workspace pipeline (fetch → graph →
  discover-docs → fetch-docs → summarize prompt) as one composed command; the
  generated README's workflow steps now reference it.
- Report PDF publishing workflow: the global skill gains
  `render-report-pdf.md` / `report-pdf-engines.md` for rendering a polished
  PDF from a Zentaizo Markdown report.
- `fetch-docs` honors a per-source `"snapshot": false` opt-out — skips the
  fetch, records `reference-only`/`snapshot-disabled`, and retires stale
  variants (tracker issue #5: login-gated doc URLs produced large, misleading
  snapshots that regenerated after deletion).

### Changed

- `session-title` derives the Claude session title from
  `<workspace>: <effort>` instead of the active slice;
  `find_active_slice()`/`slice_slug()` removed (tracker issue #3).
- Generated AGENTS.md, the global skill, and the README file tool issues at
  `DocSavage/zen-zentaizo` — the tracker moved from `DocSavage/zentaizo`
  (tracker issue #4).

### Fixed

- `pixi.lock` records the report-pdf `markdown-it-py` dependency.

## [0.15.2] - 2026-07-27

Three CLI-surface defects found by the main-0004 docs audit, where verifying a
documented claim showed the *code* to be wrong.

### Fixed

- `path slice --next --json` emitted no JSON. The parser accepted `--json`, but the `--next` branch returned before reaching the emitter, so a caller that explicitly asked for JSON got a bare id it could not parse. It now emits `{"kind": "slice", "label": …, "counter": …, "next_id": …}`. `counter` is included because the predicted number is what the command computes, and a caller should not have to parse it back out of the id; `path`, `created`, and `wrote` are omitted because no file exists yet — `"wrote": false` would make a successful prediction look like a failed allocation.
- The `graph --semantic` help text and the `graph: refreshed` follow-up message both claimed docs are read. `_graph_input_set()` places every `docs` source in `not_graphed`; only papers and notes are extracted. Both strings now say papers/notes, pinned against the input set by a test so they cannot drift apart again.
- `--repo` accepted only a filesystem path, so `--repo <name>` failed from a workspace root exactly as the generated `AGENTS.md` documents it. The contract was internally inconsistent: `AGENTS.md` documented a repo name while the parser and `docs/cli.md` documented a path. `--repo` now takes `NAME_OR_PATH` under a lexical rule — a bare name selects `repos/<name>` in the containing workspace, while anything with a path separator or a `./`, `../`, `~`, or `/` prefix keeps its filesystem meaning. The name form is validated with an **exact-directory** check: because a workspace is itself a git repo and git discovery searches upward, a mistyped name would otherwise have resolved to the workspace's own git directory and silently written the pending-authors ledger there, misattributing a later commit. A name that also matches a different git repo in the current directory is refused with both candidates named.
- `commit-trailer --repo` learned the same form. As the ledger's sole consumer, leaving it path-only would have made one `--repo <name>` token mean different repositories across a single note → trailer → clear lifecycle, and its failure mode is silent: a missed ledger prints the committer-only trailer and drops the recorded implementor. The two commands share only the lexical selector — `delegation` still refuses a non-repository path while `commit-trailer` stays tolerant of one, printing its ordinary output unchanged.

## [0.15.1] - 2026-07-26

### Fixed

- `fetch` now advances a `reference` repo pinned to a moving ref. `fetch_reference_repo` fetched and then ran `git checkout <ref>`, which switches to the *existing local branch* and leaves it where the previous fetch left it, so `zentaizo.lock.json` recorded a stale commit while labelling it with a ref that had moved on — a reproducibility defect in the mechanism the atlas/lock split exists to provide. The ref is now resolved through `resolve_upstream_sha` and the checkout is fast-forwarded onto it. A local branch that has genuinely diverged is left untouched, warns with the local and upstream shas plus a `git log --left-right` command to inspect them, and has its true HEAD recorded in the lock — recording what is actually on disk beats both discarding commits silently and lying in the lock. The dirty-tree refusal is unchanged, an immutable `ref` (tag or sha) still lands detached at exactly that object, and `fetch_edit_repo` is untouched: edit repos still keep their HEAD so in-progress work survives.

## [0.15.0] - 2026-07-26

Documentation style guide, its application across every doc, and the matching
vocabulary change in generated workspace text.

### Added

- `docs/STYLE.md`: a documentation style guide for this repository — five numbered rule groups (sentences, paragraphs, documents, diction, claims) plus a canonical-terms glossary that names the losing synonym for each concept. The claims group requires measured values with their conditions, a named baseline, limits stated alongside the capability, and a cited implementation for any claim about generated output or CLI surface.

### Changed

- **Conventions generation 5**: generated workspace text, the bundled skills, and the CLI descriptions use **agent** for the AI system doing the work, and the default atlas text, `provide-info`, the CLI descriptions, and the global skill say **Zentaizo workspace** rather than *context workspace*. Existing workspaces report conventions `behind` until the `upgrade-zentaizo` skill reconciles them.
- Canonical vocabulary across the docs: **agent** replaces *assistant*, and bare *the tool* becomes **Zentaizo** or **the Zentaizo CLI** by context. Section headings are sentence case.
- *workspace* is qualified as **Zentaizo workspace** at its first standalone use on each page, then left bare. The word names at least four other things a reader may have in mind. Compound modifiers (*workspace format*, *workspace root*) stay bare, and two uses that did not mean a Zentaizo workspace at all were reworded instead.
- Versioning policy: work on the reserved `main` effort bumps per landed slice, because `effort close main` is refused and trunk work would otherwise never get a version. One *landing* still gets one version, even when it carries several slices.

### Fixed

- Ten documented claims that no longer matched the code (main-0004), each corrected against the implementation: `zentaizo sandbox` renders two targets (`policy`, `claude`) and is a file-tool guardrail rather than the read-only enforcement the README implied; the lock is written by six commands, not only `fetch`; `next-note` emits no frontmatter and stamps no `edited_by`; `create` has five undocumented flags and `fetch-docs` one; `--json` exists on every `effort`/`path`/`next-*` command and `cache-commit-trailer`/`seed-from`/`skills`/`sandbox` were undocumented; `.graphifyignore` overlays `.gitignore` last-match-wins rather than replacing it; `graphifyy` and `trafilatura` are core dependencies and `[graph]` is an empty alias; `effort switch` also writes the registry; slice frontmatter carries seven fields, not two; and the stale `cli.py:<line>` citations in the Claude-integration doc are now symbol-only.

## [0.14.0] - 2026-07-24

### Added

- Bundled Trafilatura 2.1 main-content extraction for external single-page and in-repo HTML doc snapshots (docs-layer-0005). HTML snapshots are Markdown, keep headings/lists/tables/code while dropping page chrome and comments, pass through the existing mandatory safety scan, and record extractor version/profile plus a raw-input hash in the lock. A loud stdlib fallback preserves the prior `.txt` behavior when extraction is unavailable or fails.
- `zentaizo setup` and read-only `zentaizo setup --check` (foundations-0006). Setup detects Claude, Codex, and Gemini, prompts per harness, fails closed on non-interactive input unless the user explicitly authorizes `--yes`, preserves user-owned content, and is idempotent. The check reports harness skill state, Graphify, `git`/`gh`, and docs-scan package metadata without loading its model.

### Changed

- Graphify 0.9 is now a bounded core dependency (`>=0.9.26,<0.10`), with the historical `[graph]` extra retained as an empty compatibility alias. Graph execution resolves the active environment's module first and falls back to an external `graphify` command, so pipx installs work without separately exporting a dependency script. The managed ignore explicitly excludes `docs/snapshots/`, preserving mode-scoped graph staleness now that Graphify can traverse ordinary snapshot directories.
- **Conventions generation 4** (foundations-0006): generated `AGENTS.md` files tell agents to run `zentaizo status` once per session, surface only non-current workspace conditions without repeating unchanged alerts, and never run setup or convention upgrades without explicit user authorization. `status` now lists quarantined doc snapshots.
- Installation is two steps: install Zentaizo, then run `zentaizo setup`. Graphify and Trafilatura no longer require separate upfront install instructions.

### Fixed

- Snapshot replacement retires superseded clean and quarantined text variants before publishing the new result, preventing stale `.txt`/`.md` files and ensuring an `ok` snapshot cannot survive a later flagged quarantine.

## [0.13.0] - 2026-07-24

### Changed

- **Conventions generation 3** (integrations-0005): the knowledge graph is presented as standard usage rather than an optional extra, matching the repo README's reworked workflow. The generated workspace `README.md` gains a "Build the knowledge graph" step between fetch and summarize; the generated `AGENTS.md` consultation order says build-if-missing (`zentaizo graph`) instead of conditioning on the graph's existence; the summarize prompt nudges toward building the graph when `graphify-out/graph.json` is missing; the `provide-info` block and the global skill name the graph alongside summaries. Graceful degradation is unchanged — a workspace still works without the `graphify` binary. Existing workspaces adopt the wording via `upgrade-zentaizo`.

## [0.12.0] - 2026-07-20

### Added

- **Conventions generation 2** (feedback-0001): the generated workspace `AGENTS.md` gains a "Reporting Zentaizo Tool Issues" section — bugs, friction, or ideas about the tool or its workspace conventions are filed upstream with `gh issue create -R DocSavage/zentaizo` (confirm with the user first; fall back to a `sessions/` note when `gh` is unavailable), never silently worked around. The global skill and README carry the same procedure. Existing workspaces adopt it via `upgrade-zentaizo`.

### Removed

- The `-Z`/`--zentaizo` hub-routing flag, the `zentaizo config` command, and the tool-level hub config (feedback-0001). GitHub issues are the feedback channel a generated workspace can honestly document — `-Z` presupposed the maintainer's local filesystem layout, and `-C <path>` already covers filing a session doc into another local workspace. A leftover `~/.config/zentaizo/config.json` is now unused and can be deleted.

## [0.11.0] - 2026-07-19

### Added

- Workspace conventions tracking (foundations-0005), establishing **conventions generation 1** as the baseline: `zentaizo create` seeds `zentaizo.lock.json` with a `conventions` block (`generation` is the comparison key; `tool_version`/`stamped_at` are provenance), the new `zentaizo upgraded` verb re-stamps it when an `upgrade-zentaizo` pass finishes (recreating a missing lock only when an atlas proves the directory is a workspace), and `zentaizo status` ends with a `Conventions:` section — `current` / `behind` (per-generation delta lines from the new `CONVENTIONS_DELTAS` map plus upgrade guidance) / `not tracked` — reporting a stamp newer than the installed tool as an outdated tool. Releases that change generated workspace artifacts or session-file conventions now bump `CONVENTIONS_GENERATION` and add one delta entry (rule in `docs/design/versioning.md`); the lock fallbacks in `fetch`/`fetch-docs`/`graph` deliberately never stamp, so a pre-tracking workspace keeps reporting `not tracked` until an upgrade pass records itself.

## [0.10.3] - 2026-07-19

### Changed

- `graphify-out/` is now treated as derived output rebuilt per clone (integrations-0004): the scaffolded `.gitignore` ignores the whole directory (replacing the `cost.json`/`cache/stat-index.json` carve-outs), and the generated `AGENTS.md`/`README.md` document the policy — each clone runs `zentaizo graph` after `zentaizo fetch` (offline tree-sitter extraction, no LLM tokens, ~1 min). Motivated by real measurements: `graph.json` alone reached 97–99 MiB at a 12-repo workspace, at GitHub's hard 100 MiB per-file push limit. Repo docs aligned. Existing workspaces adopt the policy via `upgrade-zentaizo`.

## [0.10.2] - 2026-07-19

### Fixed

- `fetch-docs` no longer corrupts binary documents (docs-layer-0004): content is classified as text or binary before any decoding, so PDFs and other binary formats are never round-tripped through the Unicode sanitizer (which stripped embedded images and rewrote byte streams while reporting `ok`). Binary sources are now recorded as `reference-only` with reason `unsupported-binary` (no snapshot file, surfaced as a `NOTE`), a binary answer to the `llms.txt` probe falls through to the page tier, and the summarize prompt marks such docs "do not decode the binary source". In-repo docs classify by suffix allow/deny lists with a git-style NUL sniff for unknown suffixes; external fetches classify by media type with the same sniff, keeping response bytes undecoded until classified.

## [0.10.1] - 2026-07-19

### Added

- The `zentaizo summarize` prompt gains a graph-grounding Guidance bullet when `graphify-out/graph.json` exists: ground cross-source claims in `relationships.md` with `graphify query`/`path`/`explain` citations instead of re-scanning repos. Graph-less workspaces see no change.

### Fixed

- Version bumps are visible to the lock resolver again: `pyproject.toml` declares `[tool.uv] cache-keys` including `src/zentaizo/__init__.py`, so `pixi lock`/`pixi update` invalidate the cached path-package metadata on a bump instead of silently keeping the old version.

## [0.10.0] - 2026-07-10

Delegation-aware commit attribution (the `claude-integration` effort's ledger + nested-run arc).

### Added

- Pending-authors ledger for delegated implementation: `zentaizo delegation note|list|clear` records who authored a repo's pending changes (one uncommittable JSON entry per note under `<git-dir>/zentaizo/pending-authors/`), and `zentaizo commit-trailer` — the sole consumer — prints one `Co-authored-by:` per recorded implementor plus `Reviewed-by:` for the committing session (`--also-author` elevates the committer), with per-role dedup, a 24h staleness warning, an explicit-clear reminder, and a warn-only unnoted-Codex-session safety net. `commit-trailer` gains `--repo`.
- Codex identity resolution from the run's own rollout log (`$CODEX_HOME/sessions/…/rollout-*-<thread>.jsonl`): the bundled hook, `commit-trailer`, `cache-commit-trailer --codex`, and `zentaizo edited` now recover the model + reasoning effort a run actually used, instead of only the configured default in `config.toml`.

### Fixed

- Commits made by a Codex run delegated from inside a Claude Code session (e.g. the Codex companion plugin) are now attributed to Codex, not Claude: assistant detection is innermost-first (`CODEX_THREAD_ID` before `CLAUDECODE`) in the prepare-commit-msg hook, `commit-trailer`, and the `edited_by:` identity. When the committing assistant is known but no identity resolves, the hook emits no trailer rather than the wrong provider's.

### Changed

- The prepare-commit-msg hook's per-provider idempotency also recognizes `Reviewed-by:` lines, so it never re-adds the committer as a spurious co-author on delegated commits.

## [0.9.0] - 2026-06-23

### Added

- Tool-level hub config (`zentaizo config set|get|unset hub`) and the `--zentaizo`/`-Z` routing flag so a spoke workspace files efforts/docs into a configured hub workspace.

### Changed

- Robust global-config IO (`CliError` on corrupt/non-object JSON; atomic write).
