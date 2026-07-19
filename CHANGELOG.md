# Changelog

All notable changes to this project are documented here.

This project uses the Keep a Changelog format. Versions 0.8.0 and earlier predate this changelog.

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
