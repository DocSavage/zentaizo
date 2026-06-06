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
zentaizo create PATH
```

Creates a workspace shell with source directories, summaries directory, and assistant instructions. It does not create `zentaizo.atlas.json`; the first AI-assisted setup step is to identify the source material and create that human-authored atlas.

```bash
zentaizo validate [PATH]
```

Checks that `zentaizo.atlas.json` exists and has the required shape. Legacy `zentaizo.config.json` workspaces are still readable.

```bash
zentaizo status [PATH]
```

Shows source counts (split by role: edit vs reference) and the lock status. For each repo it inspects the working tree: edit repos report the current branch and whether they are at the locked SHA or have diverged; reference repos flag drift between HEAD and the locked SHA. When an edit repo is clean and behind its upstream, `status` prints the rebase command. If the atlas is missing, shows the setup prompt instead of failing.

```bash
zentaizo fetch [PATH] [--rebase]
```

Fetches repositories listed in `zentaizo.atlas.json` and records resolved commits in `zentaizo.lock.json`. Behavior depends on each repo's `role`:

- `role: "reference"` — re-resolves the pin (`ref`), checks it out, refuses to overwrite a dirty working tree.
- `role: "edit"` — clones and checks out `ref` on first fetch only; on subsequent fetches refreshes remotes (`git fetch --tags --prune`) but leaves HEAD and the working tree alone. If the tree is clean and HEAD is behind the freshly-resolved upstream, `fetch` prints the exact rebase command. `--rebase` runs the rebase for every clean+behind edit repo.

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
zentaizo summarize [PATH]
```

Writes a prompt for hierarchical summarization. A later version can run a configured LLM directly.

```bash
zentaizo provide-info TARGET [PATH]
```

Adds a Zentaizo reference block to `TARGET/AGENTS.md` so an assistant working in that repository knows where to look.

```bash
zentaizo edited PATH [--as IDENTITY]
```

Records that the current editor touched a frontmatter-bearing session file, appending (or, for a consecutive same-editor edit, refreshing) an entry in its `edited_by:` ledger. The editor identity is resolved deterministically: in an AI session it comes from the commit-trailer cache (the exact model + reasoning effort, the same source the commit-attribution hook reads); in a plain shell it falls back to `git config user.name`; `--as` overrides both. Entries are git-style local timestamps (`Tue Jun 2 12:41:53 2026 -0400  Claude Opus 4.8 (1M context, reasoning xhigh)`). The `next-change`/`next-debugging`/`next-report` scaffolders stamp the first entry automatically.
