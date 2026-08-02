# CLI Design

Zentaizo should feel like a normal tool:

```bash
zentaizo setup
zentaizo create my-system-atlas
zentaizo bring-up
zentaizo provide-info /path/to/repo
```

Pixi is useful for developing Zentaizo itself, but it should not be required in user-facing examples.

## How `zentaizo ...` works

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

## Initial commands

```bash
zentaizo setup [--check] [--yes]
```

Finishes one-time user-level setup after installation. It detects Claude,
Codex, and Gemini from their environment overrides
(`CLAUDE_CONFIG_DIR`/`CODEX_HOME`/`GEMINI_DIR`) or canonical config roots,
prompts before installing the global Zentaizo skill into each detected
harness, and leaves undetected harnesses untouched. Non-interactive input fails
closed unless `--yes` is supplied after the user has explicitly authorized the
changes. Existing user-owned destinations are preserved or refused under the
same rules as `zentaizo skills install`; reruns are idempotent.

`--check` is read-only. It reports harness/skill state, Graphify resolution,
`git`/`gh` availability, and whether the optional `docs-scan` distribution is
installed. The docs-scan probe reads package metadata only and never loads its
model.

```bash
zentaizo create PATH [--name NAME] [--no-skills] [--no-git] [--no-commit-hook] [--no-claude-hooks]
```

Creates a Zentaizo workspace shell with source directories, summaries directory, and agent instructions. It does not create `zentaizo.atlas.json`; the first AI-assisted setup step is to identify the source material and create that human-authored atlas. It does seed `zentaizo.lock.json` with a `conventions` stamp — the generation of workspace conventions this build scaffolds (see `zentaizo upgraded`); `zentaizo fetch` fills in the resolved sources later. By default it also installs the managed Claude `SessionStart` hook when a current `zentaizo session-title` command is available on `PATH`; pass `--no-claude-hooks` to skip that. If no managed global skill is detectable, the closeout points to `zentaizo setup`. `--name` sets the workspace display name; `--no-skills` skips copying the bundled `skills/` markdown; `--no-git` skips `git init` (and implies `--no-commit-hook`); `--no-commit-hook` git-inits but leaves the commit-attribution hook out.

```bash
zentaizo validate [PATH]
```

Checks that `zentaizo.atlas.json` exists and has the required shape. It also runs effort-doc integrity checks: missing effort docs, orphan effort docs, duplicate effort numbers, and legacy registry entries without a `number` are reported loudly. Missing or overlong `short_title` fields on open `changes/` and `debugging/` slices are warnings only. Legacy `zentaizo.config.json` workspaces are still readable.

```bash
zentaizo bring-up [PATH] [--check | --yes]
```

Runs the mechanical workspace pipeline in order: `validate`, `fetch`,
`fetch-docs`, `graph`, then `summarize`. The command calls the internal
`_validate_operation()`, `_fetch_operation()`, `_fetch_docs_operation()`,
`_graph_operation()`, and `_summarize_operation()` functions
(`src/zentaizo/cli.py`). It writes `summaries/summarize.prompt.md`; hand that
prompt to your agent to produce the summaries.

The pipeline skips `fetch-docs` when the atlas declares no `docs` sources,
including when it declares papers but no docs. It skips `graph` only when
Graphify is unavailable. A resolved Graphify failure or a managed-file refusal
stops the run. An individual doc fetch failure remains nonfatal and is recorded
as `reference-only`, matching `zentaizo fetch-docs`.

The command is not transactional. A failed step leaves earlier fetches,
snapshots, quarantined artifacts, graph output, and lock updates in place. The
failure message names the failed step and the last completed step so you can
fix the cause and rerun safely.

The command asks before it fetches or writes. Non-interactive input fails
closed unless you pass `--yes` after explicit authorization. The `--yes` flag
does not permit overwriting user-owned managed files. The `--check` flag is
read-only and prints an ordered forecast; it says which steps would be
attempted or skipped without claiming network, repository, or Graphify
success. The `--check` and `--yes` flags are mutually exclusive. These rules
are implemented by `bring_up_workspace()` (`src/zentaizo/cli.py`).

```bash
zentaizo status [PATH]
```

Shows source counts (split by role: edit vs reference) and the lock status. For each repo it inspects the working tree: edit repos report the current branch and whether they are at the locked SHA or have diverged; reference repos flag drift between HEAD and the locked SHA. When an edit repo is clean and behind its upstream, `status` prints the rebase command. It reports quarantined doc snapshots with their paths and prints one knowledge-graph line (`graph: not built` / `current` / `stale` — see `zentaizo graph`). If the atlas is missing, shows the setup prompt instead of failing.

It ends with a `Conventions:` section comparing the generation stamped in the lock's `conventions` block against the generation the installed zentaizo generates: `current` (they match), `behind` (each missed generation's `CONVENTIONS_DELTAS` line is printed, followed by the pointer to the `upgrade-zentaizo` skill), or `not tracked` (the workspace predates conventions tracking — same pointer, full reconciliation). A stamp *newer* than the installed Zentaizo CLI reports that CLI as outdated. This is the only command that reports conventions state; nothing else advises about it.

```bash
zentaizo fetch [PATH] [--rebase] [--no-graph]
```

Fetches repositories listed in `zentaizo.atlas.json` and records resolved commits in `zentaizo.lock.json`. Behavior depends on each repo's `role`:

- `role: "reference"` — re-resolves the pin (`ref`), checks it out, refuses to overwrite a dirty working tree.
- `role: "edit"` — clones and checks out `ref` on first fetch only; on subsequent fetches refreshes remotes (`git fetch --tags --prune`) but leaves HEAD and the working tree alone. If the tree is clean and HEAD is behind the freshly-resolved upstream, `fetch` prints the exact rebase command. `--rebase` runs the rebase for every clean+behind edit repo.

When the lock records a graph (see `zentaizo graph`) and a graphed source's rev changed, `fetch` also refreshes the knowledge graph best-effort — code-only (AST, offline, no model API), never failing the fetch. `--no-graph` skips it; if `graphify` is missing the fallback is a printed stale hint.

```bash
zentaizo fetch-docs [PATH] [--no-deep-scan]
```

Snapshots `docs` sources into `docs/snapshots/`, running every fetched artifact through a content-safety pass first (strips invisible/smuggling characters, flags injection signatures). `--no-deep-scan` disables the optional `docs-scan` backend; the mandatory stdlib safety pass still runs. Results are recorded under `doc_snapshots` in `zentaizo.lock.json` with a per-source status:

- **`ok`** — content was sanitized and written as a snapshot, with a content hash.
- **`flagged`** — an injection signature matched; the content is quarantined as `docs/snapshots/<name>.flagged.<ext>` and **not** surfaced as a usable snapshot until a human reviews it.
- **`reference-only`** — no local snapshot was produced; the entry keeps its source as a pointer. The `reason` is `not-fetched` (an in-repo `repo`+`path` whose repo has not been fetched yet), `no-source` (a non-http(s) URL), `fetch-error` (the fetch failed — surfaced as a loud `WARNING`), or `unsupported-binary` (a binary format such as PDF — the text pipeline would destroy it, so the source is kept as a pointer and never rewritten; surfaced as a `NOTE`).

Only text content enters the sanitize-and-write pipeline. In-repo docs are classified by suffix (an explicit text allowlist and binary denylist) with a git-style NUL sniff for unknown suffixes; external fetches are classified by media type with the same content sniff for unknown types. Binary sources are excluded from automatic summarization until a binary-aware extraction and safety policy exists.

Source handling:

- **In-repo** (`repo` + `path`) — read from the already-fetched `repos/<repo>/<path>`. No network.
- **External** (`url`) — probe `llms-full.txt`/`llms.txt` at the site root first (a single curated Markdown file), else salvage the single referenced page. HTML pages use bundled Trafilatura main-content extraction and become Markdown; in-repo `.html`/`.htm` sources use the same path. Navigation, sidebars, comments, and footers are dropped before the mandatory safety pass. Full-site mirroring and Read-the-Docs archive extraction remain deferred.

The stdlib safety pass always runs and cannot be disabled. Trafilatura extraction is versioned as profile `main-content-v1`; the lock records its version and the raw-input hash. If extraction declines, cannot import, or fails at runtime, the command falls back to the prior stdlib HTML reducer and writes `.txt`; runtime failures are loud. Publishing any new result retires prior clean/quarantined suffix variants so a stale trusted snapshot cannot survive a later quarantine. Installing the optional `zentaizo[docs-scan]` extra (LLM Guard) adds a deeper, model-based scan layered **on top of** the baseline; it auto-enables when installed. `--no-deep-scan` turns off only that optional layer (the baseline still runs). Each `doc_snapshots` entry records `baseline_scanner` and `deep_scanner` (`llm-guard` / `none` / `disabled` / `unavailable`) for audit.

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

Builds (or incrementally refreshes) a workspace-wide knowledge graph with [Graphify](https://github.com/safishamsi/graphify) — the structural counterpart to `summaries/`: one graph over `repos/`, `papers/`, and `notes/` whose cross-repo and code↔doc edges no per-repo run can see. Graphify is a core dependency: resolution prefers the active environment's bundled module (`python -m graphify`), which works under pipx, then falls back to an external `graphify` on `PATH` for source environments missing dependencies. Graphify's query surface (`graphify query` / `path` / `explain`, MCP) remains native and is never wrapped.

Two modes:

- **Default — code-only, fully offline.** AST extraction (`graphify update`): no key, no network. Markdown gets shallow structural nodes (file + headings) on the same pass.
- **`--semantic` — opt-in full-corpus extraction** of papers and notes through a model API. Requires an explicit `--backend` (`ollama` is fully local, `claude-cli` uses the local Claude Code CLI with no key; remote backends are your explicit call) — `--semantic` without `--backend` is an error, never key auto-detection. The backend (and `--model`, if given) is recorded in the lock.

Mechanics: the command writes a managed `.graphifyignore` at the workspace root (marker comment, regenerated per build; a user-owned file without the marker is refused) that scopes Graphify to the source trees. Graphify 0.9.x overlays it on `.gitignore`, so the managed file explicitly re-includes the gitignored `repos/` tree and then applies Zentaizo's exclusions. Output lands in upstream-fixed `graphify-out/`, which is derived output and not committed (the scaffolded `.gitignore` ignores the whole directory — `graph.json` alone can sit near GitHub's 100 MiB per-file limit); each clone rebuilds it locally with `zentaizo graph` after `zentaizo fetch`. `GRAPH_REPORT.md` goes through the same safety pass as fetched docs; a flagged report is moved aside to `GRAPH_REPORT.flagged.md` (nothing left in place) and recorded as `report_status: flagged`. The lock gains a `graph` block — mode, exact backend version, and a mode-scoped `built_from` (each graphed source's locked identity) plus `not_graphed` (excluded sources mapped to reasons). The tested compatibility range is Graphify 0.9.26 through the 0.9 series. Graphify 0.9.x can traverse ordinary `snapshots` directories, so Zentaizo explicitly excludes `docs/snapshots/` to keep doc-summary and graph staleness as separate layers.

`zentaizo status` reports the graph line (`not built` / `current` / `stale: N source(s) changed`), counting `not_graphed` sources and surfacing a flagged report; staleness is a pure lock diff scoped to the recorded mode, so a doc hash change never stales a code-only graph. `--force` passes Graphify's own `--force` (from-scratch rebuild; covers a shrinking graph).

```bash
zentaizo provide-info TARGET [PATH]
```

Adds a Zentaizo reference block to `TARGET/AGENTS.md` so an agent working in that repository knows where to look.

```bash
zentaizo commit-trailer [--claude | --codex] [--repo NAME_OR_PATH] [--also-author]
```

Prints the current AI agent's canonical attribution trailer(s) to stdout so they can be pasted into a commit body. Provider detection uses the active agent environment, **innermost agent first**: `CODEX_THREAD_ID` is injected by the codex CLI only into the shells of a live Codex run, while `CLAUDECODE` is inherited by everything a Claude Code session spawns — including delegated Codex runs — so when both are present the commit is attributed to Codex. (`--claude` or `--codex` forces a provider, including from a non-AI shell or CI job that has the provider cache/config available.) The command reads the same commit-trailer cache used by the bundled `prepare-commit-msg` hook and by `zentaizo edited`; the Codex identity falls back from the thread-keyed cache entry to the run's own rollout log (`$CODEX_HOME/sessions/…/rollout-*-<thread>.jsonl`, which records the model + effort the run actually used), then the cache `latest.json`, then the configured default in `config.toml`, and a rollout/config resolution repopulates the cache. Unlike the hook, this command fails loudly with no stdout and a stderr reason when attribution cannot be resolved. It does not fall back to `git config user.name`.

`commit-trailer` is also the **sole consumer of the pending-authors ledger** (see `zentaizo delegation`). Its `--repo` option accepts the `NAME_OR_PATH` form described below. The default is the current directory, and any explicit path inside the repo works. When the target repo has pending delegation entries, the command prints one `Co-authored-by:` per recorded implementor (`role: "author"` entries, oldest note first — other roles are skipped with a stderr warning) followed by `Reviewed-by:` for the committing session; `--also-author` additionally credits the committer as `Co-authored-by:` when it wrote code too. Identities are deduplicated per role, so a committer that already appears as a ledger author gets both lines exactly once. On a non-empty ledger it reminds on stderr to run `zentaizo delegation clear` after the commit lands, and warns (without dropping anything) when an entry is older than 24 hours. With an empty ledger, stdout is the single `Co-authored-by:` line, unchanged; as a warn-only safety net, if the Codex cache shows a session more recent than the repo's last commit while the ledger is empty, a stderr nudge suggests `zentaizo delegation note --codex`.

```bash
zentaizo delegation note (--claude | --codex) [--repo NAME_OR_PATH] [--as IDENTITY] [--max-age HOURS]
zentaizo delegation list [--repo NAME_OR_PATH]
zentaizo delegation clear [--repo NAME_OR_PATH] [--id ID]
```

Records who *authored* a repo's pending changes when implementation was delegated to another agent (e.g. Claude orchestrates, Codex implements) so commit attribution reflects authorship, not just the committing environment. The ritual: **`note` when the delegated run returns → `commit-trailer` at commit → `clear` after the commit lands.** Run `note` once per touched repo, at review time rather than dispatch, so the freshest cache entry is the delegated run itself.

`NAME_OR_PATH` uses a lexical rule implemented by `_select_repo_dir()` (`src/zentaizo/cli.py`). A bare name selects the exact `repos/NAME` git repository in the containing Zentaizo workspace. A value with a path separator, or one starting with `./`, `../`, `~`, or `/`, remains a filesystem path. If a bare name also identifies a different git repository in the current directory, the command errors and names both candidates.

Each `note` writes one JSON entry file (`{id, provider, model, effort, identity, role, noted_at, source}`) under `<git-dir>/zentaizo/pending-authors/` in the target repo — uncommittable and per-checkout by construction (the git dir is discovered from any path inside the repo, resolving worktree/submodule `gitdir:` pointer files), and safe under concurrent notes because entries never share a file. Identity resolution precedence, with each entry recording its `source`: the session/thread-keyed commit-trailer cache entry, then the cache `latest.json` only if captured within `--max-age` (default 6 hours), then — Codex only — the configured default from `config.toml` with a stderr warning that it may not be the model the delegated run used (`source: "config"`), and `--as "<identity>"` bypasses resolution entirely (`source: "override"`). When nothing resolves, `note` fails loudly and suggests `--as`. `list` shows each pending entry with its age and source; `clear` empties the ledger (or removes one entry with `--id`) — clearing is always explicit, never a side effect of committing.

```bash
zentaizo edited PATH [--as IDENTITY]
```

Records that the current editor touched a frontmatter-bearing session file, appending (or, for a consecutive same-editor edit, refreshing) an entry in its `edited_by:` ledger. The editor identity is resolved deterministically: in an AI session it comes from the commit-trailer cache (the exact model + reasoning effort, the same source the commit-attribution hook reads), detecting the innermost agent first (a Codex run delegated from a Claude session stamps Codex); Codex sessions fall back to the run's own rollout log, then local Codex config, and populate that cache when it is missing. In a plain shell it falls back to `git config user.name`; `--as` overrides both. Entries are git-style local timestamps (`Tue Jun 2 12:41:53 2026 -0400  Claude Opus 4.8 (1M context, reasoning xhigh)`). The `effort new`, `next-change`, `next-debugging`, `next-brainstorming`, `next-handoff`, and `next-report` scaffolders stamp the first entry automatically.

```bash
zentaizo upgraded [PATH]
```

Records that an `upgrade-zentaizo` pass brought the workspace to the installed conventions generation, re-stamping the lock's `conventions` block (`generation` is the comparison key `zentaizo status` reads; `tool_version` and `stamped_at` are provenance). It mirrors `zentaizo edited`: the stamp is CLI-written, never hand-written — the `upgrade-zentaizo` skill runs it as its final step, and `zentaizo create` writes the initial stamp for fresh workspaces. If the lock is missing it is recreated from scratch and stamped (the atlas must exist, so an arbitrary directory is never stamped). Prints a one-line confirmation naming the generation.

```bash
zentaizo claude-hooks [PATH]
```

Installs or refreshes the managed Claude `SessionStart` hook in `.claude/settings.json`, preserving user-authored settings and hooks. It probes the `zentaizo` executable on `PATH` first and refuses to write a hook if that executable is missing or too old to support `session-title`.

```bash
zentaizo session-title
```

Claude hook command, not a normal user workflow command. It reads `SessionStart` JSON on stdin and emits a `sessionTitle` of the form `<workspace>: <effort>` — the workspace directory name plus the current effort label (`main` included). Launching from a subdirectory (e.g. a vendored repo) still titles the session after the containing workspace; outside any workspace the title falls back to the directory name.

## Efforts and session files

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

Every command in this section accepts `-C PATH` / `--workspace PATH` to target a workspace other than the current directory (it defaults to `.`).

Every command in this section also accepts `--json`, as does `zentaizo edited`: each
`effort` operation, each `path` operation, and each `next-*` allocator. The payload is
the machine-readable form of what the command prints — an allocator emits the created
file's kind, label, and workspace-relative path (`_emit_created`), and a `path` lookup
emits the resolved path and its kind (`_emit_path`).

## Other commands

```bash
zentaizo sandbox [WORKSPACE] [--target {policy,claude}] [--mode {implement,curate}] [--check]
```

Derives a least-privilege access policy from the atlas's `edit`/`reference` roles and
renders it. `--target policy` (the default) prints the computed policy as JSON with no
side effects; `--target claude` merges managed `Edit`/`Write` deny rules into
`<workspace>/.claude/settings.json`, preserving unmanaged entries. `--mode` selects the
writable set, and `--check` renders without writing and exits nonzero when the config
has drifted from the atlas. The `claude` target is a file-tool guardrail, not a security
boundary — see `docs/design/sandboxing.md`.

```bash
zentaizo seed-from SOURCE [TARGET] [--accept-all] [--dry-run]
```

Walks another workspace's atlas and offers each repo, doc, paper, and note for the
target atlas, copying local files referenced by `path:`. `--accept-all` skips the
prompts; `--dry-run` previews without writing. Repos are re-pinned declaratively, so
`zentaizo fetch` populates the working tree afterward rather than a copy of `repos/`.

```bash
zentaizo skills {list,install,uninstall}
```

Manages the global Zentaizo skill in each detected harness's configuration.

```bash
zentaizo cache-commit-trailer (--claude | --codex)
```

Records the calling agent's identity in the commit-trailer cache that
`zentaizo commit-trailer`, `zentaizo edited`, and the bundled `prepare-commit-msg` hook
all read. It exists so a harness can populate that cache from a hook rather than having
a model name itself.
