# CLI Design

Zentaizo should feel like a normal tool:

```bash
zentaizo create my-system-atlas
zentaizo fetch
zentaizo discover-docs
zentaizo fetch-docs
zentaizo summarize
zentaizo provide-info /path/to/repo
```

Pixi is useful for developing Zentaizo itself, but it should not be required in user-facing examples.

## How `zentaizo ...` Works

The Python package declares a console script in `pyproject.toml`:

```toml
[project.scripts]
zentaizo = "zentaizo.cli:main"
```

After installation, Python creates a command named `zentaizo` that calls `zentaizo.cli:main`.

For development:

```bash
python -m pip install -e .
zentaizo --help
```

For isolated local use:

```bash
pipx install -e .
zentaizo --help
```

With Pixi:

```bash
pixi install
pixi run install-cli
zentaizo --help
```

The design rule is that `zentaizo` is the product interface. `python -m zentaizo`, `pipx`, and `pixi` are bootstrap paths.

## Initial Commands

```bash
zentaizo create PATH [--no-claude-hooks]
```

Creates a workspace shell with source directories, summaries directory, and assistant instructions. It does not create `zentaizo.atlas.json`; the first AI-assisted setup step is to identify the source material and create that human-authored atlas. By default it also installs the managed Claude `SessionStart` hook when a current `zentaizo session-title` command is available on `PATH`; pass `--no-claude-hooks` to skip that.

```bash
zentaizo validate [PATH]
```

Checks that `zentaizo.atlas.json` exists and has the required shape. It also runs effort-doc integrity checks: missing effort docs, orphan effort docs, duplicate effort numbers, and legacy registry entries without a `number` are reported loudly. Missing or overlong `short_title` fields on open `changes/` and `debugging/` slices are warnings only. Legacy `zentaizo.config.json` workspaces are still readable.

```bash
zentaizo status [PATH]
```

Shows source counts (split by role: edit vs reference) and the lock status. For each repo it inspects the working tree: edit repos report the current branch and whether they are at the locked SHA or have diverged; reference repos flag drift between HEAD and the locked SHA. When an edit repo is clean and behind its upstream, `status` prints the rebase command. Also prints one knowledge-graph line (`graph: not built` / `current` / `stale` — see `zentaizo graph`). If the atlas is missing, shows the setup prompt instead of failing.

```bash
zentaizo fetch [PATH] [--rebase] [--no-graph]
```

Fetches repositories listed in `zentaizo.atlas.json` and records resolved commits in `zentaizo.lock.json`. Behavior depends on each repo's `role`:

- `role: "reference"` — re-resolves the pin (`ref`), checks it out, refuses to overwrite a dirty working tree.
- `role: "edit"` — clones and checks out `ref` on first fetch only; on subsequent fetches refreshes remotes (`git fetch --tags --prune`) but leaves HEAD and the working tree alone. If the tree is clean and HEAD is behind the freshly-resolved upstream, `fetch` prints the exact rebase command. `--rebase` runs the rebase for every clean+behind edit repo.

When the lock records a graph (see `zentaizo graph`) and a graphed source's rev changed, `fetch` also refreshes the knowledge graph best-effort — code-only (AST, offline, no model API), never failing the fetch. `--no-graph` skips it; if `graphify` is missing the fallback is a printed stale hint.

```bash
zentaizo fetch-docs [PATH]
```

Snapshots `docs` sources into `docs/snapshots/`, running every fetched artifact through a content-safety pass first (strips invisible/smuggling characters, flags injection signatures). Results are recorded under `doc_snapshots` in `zentaizo.lock.json` with a per-source status:

- **`ok`** — content was sanitized and written as a snapshot, with a content hash.
- **`flagged`** — an injection signature matched; the content is quarantined as `docs/snapshots/<name>.flagged.<ext>` and **not** surfaced as a usable snapshot until a human reviews it.
- **`reference-only`** — no local snapshot was produced; the entry keeps its source as a pointer. The `reason` is `not-fetched` (an in-repo `repo`+`path` whose repo has not been fetched yet), `no-source` (a non-http(s) URL), or `fetch-error` (the fetch failed — surfaced as a loud `WARNING`).

Source handling:

- **In-repo** (`repo` + `path`) — read from the already-fetched `repos/<repo>/<path>`. No network.
- **External** (`url`) — a stdlib fetch cascade: probe `llms-full.txt`/`llms.txt` at the site root first (a single curated Markdown file), else salvage the single referenced page (HTML reduced to text). Full-site mirroring and Read-the-Docs archive extraction are deferred to the optional `[docs-rich]` extra.

The stdlib safety pass always runs and cannot be disabled. Installing the optional `zentaizo[docs-scan]` extra (LLM Guard) adds a deeper, model-based scan layered **on top of** the baseline; it auto-enables when installed. `--no-deep-scan` turns off only that optional layer (the baseline still runs). Each `doc_snapshots` entry records `baseline_scanner` and `deep_scanner` (`llm-guard` / `none` / `disabled` / `unavailable`) for audit.

```bash
zentaizo discover-docs [PATH]
```

Read-only scan of the fetched `repos/` for in-repo doc sources — OpenAPI/Swagger specs, GraphQL schemas, `.proto` files, and `llms.txt`/`llms-full.txt` — and prints ready-to-paste `docs` atlas entries (`repo` + `path`). It also flags doc-site configs (`.readthedocs.yaml`, `mkdocs.yml`, `docs/conf.py`) so you can add an external `url` entry once you know the published URL. Sources already listed in the atlas are skipped; noisy/vendored directories are pruned. Writes nothing — paste the entries you want into `zentaizo.atlas.json` yourself.

```bash
zentaizo summarize [PATH] [--force|--all] [--focus TEXT]
```

Writes a prompt for hierarchical summarization. **Incremental:** each `summaries/sources/<name>.md` carries a `source_rev` frontmatter line pinning it to the source's locked identity (repo `commit`/`head`, doc `content_hash`); the command diffs that against `zentaizo.lock.json` and asks only for sources that are new or changed, keeping the rest. Legacy summaries without `source_rev` fall back to a timestamp check (source `fetched_at` vs the summary's git/mtime). Flagged doc snapshots are surfaced for review rather than summarized. `--force`/`--all` regenerates everything; `--focus TEXT` adds a per-run framing emphasis. A later version can run a configured LLM directly.

```bash
zentaizo graph [PATH] [--semantic --backend NAME [--model NAME]] [--force] [--no-deep-scan]
```

Builds (or incrementally refreshes) a workspace-wide knowledge graph with [Graphify](https://github.com/safishamsi/graphify) — the structural counterpart to `summaries/`: one graph over `repos/`, `papers/`, and `notes/` whose cross-repo and code↔doc edges no per-repo run can see. The `graphify` binary must already be on `PATH` (`uv tool install graphifyy`, or `pip install "zentaizo[graph]"`); the command never installs it, and Graphify's query surface (`graphify query` / `path` / `explain`, MCP) is used directly, never wrapped.

Two modes:

- **Default — code-only, fully offline.** AST extraction (`graphify update`): no key, no network. Markdown gets shallow structural nodes (file + headings) on the same pass.
- **`--semantic` — opt-in full-corpus extraction** of papers and notes through a model API. Requires an explicit `--backend` (`ollama` is fully local, `claude-cli` uses the local Claude Code CLI with no key; remote backends are your explicit call) — `--semantic` without `--backend` is an error, never key auto-detection. The backend (and `--model`, if given) is recorded in the lock.

Mechanics: the command writes a managed `.graphifyignore` at the workspace root (marker comment, regenerated per build; a user-owned file without the marker is refused) that scopes Graphify to the source trees — Graphify reads it *instead of* the workspace `.gitignore`, which is what makes the gitignored `repos/` graphable. Output lands in upstream-fixed `graphify-out/` and is committed except `cost.json` and `cache/stat-index.json`. `GRAPH_REPORT.md` goes through the same safety pass as fetched docs; a flagged report is moved aside to `GRAPH_REPORT.flagged.md` (nothing left in place) and recorded as `report_status: flagged`. The lock gains a `graph` block — mode, backend version, and a mode-scoped `built_from` (each graphed source's locked identity) plus `not_graphed` (excluded sources mapped to reasons). Known upstream limit (graphifyy 0.8.39): any directory named `snapshots` is skip-listed, so `docs/snapshots/` cannot be graphed in either mode and is always listed under `not_graphed`.

`zentaizo status` reports the graph line (`not built` / `current` / `stale: N source(s) changed`), counting `not_graphed` sources and surfacing a flagged report; staleness is a pure lock diff scoped to the recorded mode, so a doc hash change never stales a code-only graph. `--force` passes Graphify's own `--force` (from-scratch rebuild; covers a shrinking graph).

```bash
zentaizo provide-info TARGET [PATH]
```

Adds a Zentaizo reference block to `TARGET/AGENTS.md` so an assistant working in that repository knows where to look.

```bash
zentaizo commit-trailer [--claude | --codex]
```

Prints the current AI assistant's canonical `Co-authored-by:` trailer to stdout so it can be pasted into a commit body. Provider detection uses the active assistant environment (`CLAUDECODE`, then `CODEX_THREAD_ID`); `--claude` or `--codex` forces a provider, including from a non-AI shell or CI job that has the provider cache/config available. The command reads the same commit-trailer cache used by the bundled `prepare-commit-msg` hook and by `zentaizo edited`; Codex can fall back to local Codex config and populate the cache when it is missing. Unlike the hook, this command fails loudly with no stdout and a stderr reason when attribution cannot be resolved. It does not fall back to `git config user.name`.

```bash
zentaizo edited PATH [--as IDENTITY]
```

Records that the current editor touched a frontmatter-bearing session file, appending (or, for a consecutive same-editor edit, refreshing) an entry in its `edited_by:` ledger. The editor identity is resolved deterministically: in an AI session it comes from the commit-trailer cache (the exact model + reasoning effort, the same source the commit-attribution hook reads); Codex sessions fall back to local Codex config and populate that cache when it is missing. In a plain shell it falls back to `git config user.name`; `--as` overrides both. Entries are git-style local timestamps (`Tue Jun 2 12:41:53 2026 -0400  Claude Opus 4.8 (1M context, reasoning xhigh)`). The `effort new`, `next-change`, `next-debugging`, `next-brainstorming`, `next-handoff`, and `next-report` scaffolders stamp the first entry automatically.

```bash
zentaizo claude-hooks [PATH]
```

Installs or refreshes the managed Claude `SessionStart` hook in `.claude/settings.json`, preserving user-authored settings and hooks. It probes the `zentaizo` executable on `PATH` first and refuses to write a hook if that executable is missing or too old to support `session-title`.

```bash
zentaizo session-title
```

Claude hook command, not a normal user workflow command. It reads `SessionStart` JSON on stdin and emits a `sessionTitle` derived from the active slice `short_title`, active slice slug, current non-main effort label, or workspace directory name.

## Efforts and Session Files

```bash
zentaizo effort new [LABEL] [--describe TEXT] [--repo NAME[=BRANCH]]...
```

Creates an effort, assigns the next registry-owned number, writes `sessions/efforts/NNNN-<label>.md` from `skills/effort-template.md`, stamps `created` and `edited_by`, records any repos/branches in `sessions/efforts.json`, makes the effort current, and prints the doc path. If `LABEL` is omitted, a deterministic themed label is chosen. `--describe` is the registry's canonical short description and also seeds the opening line of the doc as scaffold text only.

```bash
zentaizo effort list
zentaizo effort show [LABEL]
zentaizo effort switch LABEL
zentaizo effort set-branch LABEL --repo NAME[=BRANCH] [--base SHA]
zentaizo effort close LABEL
```

`effort list` shows all efforts and marks the current one. `effort show` prints the effort doc path, description, repos/branches, and slices. `effort switch` changes the current pointer. `effort set-branch` records repo participation: bare `--repo NAME` attaches a repo with no branch yet (`branch: null`, `base: null`), while `--repo NAME=BRANCH` records a real branch and computes the merge base when possible. Bare `--repo NAME` refuses to erase an existing recorded branch; pass `NAME=BRANCH` to update it. `effort close` closes non-main efforts; `main` is the uncloseable deliverable trunk.

```bash
zentaizo path effort [LABEL]
zentaizo path slice <ID>
zentaizo path slice --next
zentaizo path active
zentaizo path handoff <ID>
```

`path effort` resolves the effort doc from the registry number and label. `path slice` recovers an existing `changes/` or `debugging/` file by numeric id; `--next` previews the next `<label>-NNNN` id without writing. `path active` resolves the highest open plan for the current effort. `path handoff` lists handoffs tied to a slice id.

```bash
zentaizo next-change SLUG [--short-title TEXT]
zentaizo next-debugging SLUG [--short-title TEXT]
zentaizo next-handoff ID [TOPIC]
zentaizo next-brainstorming SLUG
zentaizo next-note SLUG
zentaizo next-report SLUG
```

These commands allocate session files through the CLI. `next-change` and `next-debugging` share the per-effort slice counter and scaffold frontmatter from `skills/plan-template.md`; `--short-title` fills the `short_title` frontmatter field and rejects values over 30 characters. `next-handoff` creates a per-slice handoff letter without consuming the slice counter. `next-brainstorming` writes a dated, provenance-bearing planning input under `sessions/brainstorming/`; raw freeform dumps are still allowed there. `next-note` writes a dated Q&A log under `sessions/questions/`. `next-report` writes a living report under `sessions/reports/`.
