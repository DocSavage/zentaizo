# Workspace Format

A Zentaizo workspace is a local context atlas for one broader system.

```text
my-system-atlas/
  AGENTS.md
  README.md
  zentaizo.atlas.json       # created after source discovery
  zentaizo.lock.json        # seeded by create (conventions stamp); sources written by fetch
  .gitignore                # does not list repos/; see "How git and root searches see repos/"
  .ignore                   # shows repos/ to rg (CLI-managed search block)

  repos/
  docs/
  papers/
  notes/
  summaries/
  sessions/
    efforts.json            # effort registry (seeded with numbered `main`)
    efforts/                # effort-level plan docs
  skills/
    curate-atlas.md         # model-agnostic interview procedure
    plan-and-implement.md   # the plan -> execute -> close-out lifecycle
    brainstorming-template.md # scaffold for provenance-bearing brainstorming docs
    effort-template.md      # scaffold for effort-level plan docs
    plan-template.md        # scaffold for changes/ and debugging/ files
    report-template.md      # scaffold for reports/ files
```

New workspaces intentionally start without `zentaizo.atlas.json`. Its absence is a setup prompt: start an AI session in the workspace, use the generated `AGENTS.md` instructions, and create the atlas after identifying the relevant source material.

## `zentaizo.atlas.json`

This file is human-authored. It says which sources belong to the system, why they matter, and whether each repo will be edited or only consulted.

```json
{
  "version": 1,
  "name": "link-shortener",
  "description": "A small multi-repo URL shortener system",
  "sources": {
    "repos": [
      {
        "name": "shortener-api",
        "url": "https://github.com/example/shortener-api.git",
        "ref": "main",
        "role": "edit",
        "description": "REST API for creating and resolving short links"
      },
      {
        "name": "deployment",
        "url": "https://github.com/example/shortener-deployment.git",
        "ref": "v1.4.2",
        "role": "reference",
        "description": "Deployment configuration pinned to a release tag"
      }
    ],
    "docs": [
      {
        "name": "api-docs",
        "kind": "api-reference",
        "url": "https://example.com/shortener/api",
        "description": "Public API documentation"
      },
      {
        "name": "shortener-openapi",
        "kind": "spec",
        "repo": "shortener-api",
        "path": "openapi/openapi.yaml",
        "description": "OpenAPI spec living inside the API repo"
      }
    ],
    "papers": [],
    "notes": []
  }
}
```

### Doc `kind` and source

Each `docs` entry may carry an optional `kind`, one of `api-reference`, `guide`, `tutorial`, `spec`, or `changelog`. It is used to order how an agent consults docs (an `api-reference`/`spec` is the abbreviated layer between summaries and raw code) and is otherwise advisory.

A doc entry names its source one of two ways, never both:

- **External** — a `url` pointing at a documentation site (readthedocs/Sphinx/MkDocs, an `llms.txt`, an OpenAPI URL, etc.).
- **In-repo** — a `repo` (the `name` of a repo source in this atlas) plus a `path` relative to that repo's fetched tree, for an API definition that already ships in the code (e.g. an `openapi.yaml`). `validate` checks that the referenced repo exists and that a `path` is given; the file itself is resolved under `repos/<repo>/<path>` after `zentaizo fetch`, so it is not required to exist at validation time.

A doc entry may also declare `"snapshot": false` (boolean; `validate` rejects other types) when the source should stay a citable pointer with no snapshot attempted — typically a login-gated page whose fetch would capture the site's generic index instead of the article. `zentaizo fetch-docs` records such an entry as `reference-only` with reason `snapshot-disabled` and removes any previously-written snapshot variants.

### Repo `role`

Each repo entry carries an optional `role` field. Two values are supported, with `reference` as the default when the field is omitted:

- `role: "edit"` — code the user will modify in this workspace. The `ref` is a starting point. `zentaizo fetch` clones and checks out `ref` only on the first fetch; after that it refreshes remotes and leaves the working tree alone, so branches and commits-in-progress survive future fetches. If the working tree is clean and HEAD is behind the upstream `ref`, `fetch` prints the rebase command; `zentaizo fetch --rebase` runs it.
- `role: "reference"` — code consulted but not changed. The `ref` is a pin. `zentaizo fetch` re-resolves it on every run (so `ref: main` tracks main; pin to a SHA or tag if you want stability) and refuses to overwrite a dirty working tree.

The split lets one workspace hold related repos the way a monorepo does, and it doubles as the access policy `zentaizo sandbox` renders: editable repos writable, reference repos denied to the agent's file tools. See `docs/design/sandboxing.md` for what that does and does not enforce.

`zentaizo fetch` also mirrors the roles into the workspace root `AGENTS.md`, as a CLI-managed block between `<!-- BEGIN zentaizo repo-roles -->` and `<!-- END zentaizo repo-roles -->` markers (see `zentaizo fetch` in `docs/cli.md`). The atlas stays the source of truth, so change roles there and re-run `fetch`, never edit the block. The block exists for readers that load `AGENTS.md` but never see tool output, such as harness permission layers. Content outside the markers is the workspace's own and is never touched.

Use branches or tags while exploring. Use commits when you need a fully reproducible snapshot.

### Repo `search_exclude`

A repo entry may carry an optional `search_exclude` list. Each item is a gitignore-style pattern, relative to that repo's root, for a path that searches from the workspace root should skip. A vendored copy of a library is the usual case:

```json
{
  "name": "shortener-api",
  "url": "https://github.com/example/shortener-api.git",
  "ref": "main",
  "role": "edit",
  "search_exclude": ["third_party/boost/"]
}
```

`zentaizo fetch` writes each item as `/repos/<name>/<item>` into the search blocks of `.ignore` and `.gitignore`, so both `rg` and Claude Code's `grep` skip it (see the next section). `validate` rejects a value that is not a list. It also rejects an item that is empty, that starts with `/`, `!` or `#`, or that contains a `..` segment, a backslash or a newline. `fetch` leaves an invalid item out of the blocks and warns about it.

## How git and root searches see `repos/`

Git must not see `repos/`, because each repo there has its own history. Searches from the workspace root should see it, because agents expect a root search to cover the code. Three files do both. In a workspace whose `shortener-api` repo vendors a copy of Boost, they look like this:

```text
# .git/info/exclude (per clone, not committed; zentaizo adds two lines and keeps the rest)
# zentaizo: hide repos/ from git; .ignore shows it to rg
/repos/

# .ignore (committed)
# BEGIN zentaizo search
# Written by `zentaizo fetch` from zentaizo.atlas.json; edit the atlas, not this block.
!/repos/
/repos/shortener-api/third_party/boost/
# END zentaizo search

# .gitignore (committed)
.zentaizo/
tmp/
docs/snapshots/*.flagged.*
# repos/ is hidden from git by .git/info/exclude, which `zentaizo fetch` writes.
# BEGIN zentaizo search
# Written by `zentaizo fetch` from zentaizo.atlas.json; edit the atlas, not this block.
/repos/shortener-api/third_party/boost/
# END zentaizo search
```

- **Git** ignores `repos/` through each clone's `.git/info/exclude`. `zentaizo create` writes the two lines after `git init`. `zentaizo fetch` writes them before it clones anything, so every clone gets them on its first fetch. They are added only when no line already hides all of `repos/` (`repos/`, `/repos/`, `repos` or `/repos`), and every other line stays. Nothing is written when the workspace is not the top level of its own git repo, for example a directory inside another repo.
- **Claude Code's `grep`** runs ugrep with `--ignore-files`, which reads only `.gitignore` files. The workspace `.gitignore` does not list `repos/`, so a root search covers it, and each repo's own `.gitignore` still applies inside that repo. A plain GNU `grep -r` reads no ignore files at all.
- **`rg`** reads `.gitignore`, `.git/info/exclude` and `.ignore`, and `.ignore` takes precedence. Its `!/repos/` line shows `repos/` to rg despite the exclude. Inside a nested git repo, rg stops applying an outer `.gitignore` but still applies an outer `.ignore`. That is why each vendored path goes in both blocks.
- **Every pattern is anchored**: `/repos/`, `!/repos/` and `/repos/<name>/<item>`. An unanchored `!repos/` would also show rg a nested repo's own ignored `repos/` directory.
- **Symlinked repos are skipped.** `rg` and `grep -r` do not follow symlinks, so a root search skips a repo that `repos/` holds as a symlink. Search it by path, for example `rg PATTERN repos/<name>/`, or replace the symlink with a clone or a git worktree. A worktree is searched like a clone. `zentaizo fetch` warns about each symlinked repo, and `zentaizo status` names them.

`zentaizo fetch` renders both blocks from the whole atlas, also on a scoped fetch, and rewrites a file only when its block changed. It never writes over unpaired or misordered markers. The `.ignore` block always exists, because it carries `!/repos/`. The `.gitignore` block exists only while some repo has a `search_exclude` item. Lines outside the markers belong to the workspace.

A workspace from before conventions generation 7 lists `repos/` in `.gitignore`. `fetch` writes the exclude and both blocks there too. That is safe: rg starts to see `repos/`, and git still hides it. The `upgrade-zentaizo` skill then deletes the `repos/` line. Every other clone must run `zentaizo fetch` right after it pulls that change. Until then, its `git status` lists every repo as untracked, and `zentaizo status` reports `Search: exclude missing`.

## `zentaizo.lock.json`

This file is machine-authored. It records what was actually fetched. `zentaizo create` seeds it with empty sources and a `conventions` stamp; `zentaizo fetch` fills in resolved source versions once an atlas exists.

The `conventions` block records which generation of workspace conventions scaffolded (or last upgraded) this workspace:

```json
"conventions": {
  "generation": 4,
  "tool_version": "0.14.0",
  "stamped_at": "2026-07-24T16:00:00+00:00"
}
```

`generation` is the comparison key — `zentaizo status` diffs it against the generation the installed tool generates and reports `current` / `behind` / `not tracked`; `tool_version` and `stamped_at` are provenance. The block is written by `zentaizo create` and re-stamped by `zentaizo upgraded` (the `upgrade-zentaizo` skill's final step), never by hand. A workspace without the block predates conventions tracking.

For repositories, the lock should include:

- source name
- URL
- requested ref
- resolved commit SHA
- local path
- dirty status
- fetch time

Doc snapshots are recorded in the top-level `doc_snapshots` list. Every entry
records the source/fetcher, snapshot or quarantine path, content hash, fetch
time, status, and safety provenance. HTML snapshots also carry structured
extraction provenance:

```json
"extraction": {
  "extractor": "trafilatura",
  "version": "2.1.0",
  "profile": "main-content-v1",
  "raw_input_hash": "sha256:..."
}
```

Trafilatura output is Markdown (`<name>.md`). The raw-input hash separates an
upstream page change from an extractor-output change, while `content_hash`
always hashes the bytes written to the snapshot or quarantine. A normal
extractor decline, missing dependency, or runtime failure falls back to the
stdlib HTML reducer (`<name>.txt`) and records `extractor: "stdlib"` plus the
raw-input hash and a `fallback_reason`; runtime failures also print a warning.
Only one clean/quarantined text variant survives a refresh. Binary sources are
`reference-only` and have no converted snapshot.

A lock from before conventions generation 7 may still carry a top-level `graph` block, left by the retired knowledge-graph layer. No command reads it, and `zentaizo upgraded` deletes it.

## Summaries

Summaries should form a level-of-detail hierarchy:

```text
summaries/
  overview.md
  relationships.md
  open-questions.md
  sources/
    shortener-api.md
    shortener-web.md
    shortener-client.md
```

The agent should read summaries before scanning source code.

## Sessions

Sessions are the durable trail of how the workspace has been used:

```text
sessions/
  efforts.json     # registry: effort labels, numbers, current pointer, per-repo branch/base
  efforts/         # effort-level plan docs
  brainstorming/   # pre-decision input (scaffolded or freeform)
  changes/         # implementation plans (slices)
  debugging/       # plan-shaped bug investigations (shares the changes/ counter)
  questions/       # dated Q&A logs
  handoffs/        # paste-ready execution prompts for the implementing agent
  reports/         # living evidence-backed syntheses
```

Work is grouped into **efforts** — named bodies of work that may span several
editable repos. `sessions/efforts.json` owns each effort's label, number,
status, current pointer, and repo branch/base map. `sessions/efforts/NNNN-<label>.md`
is the human-authored effort plan doc; the CLI derives its path from the
registry number and label.

The effort label, not a git branch, prefixes a slice's filename
(`<label>-NNNN-<slug>.md`). The CLI allocates every session file — `zentaizo
effort new`, then `zentaizo next-change` / `next-debugging` / `next-handoff` /
`next-brainstorming` / `next-note` / `next-report` — so scaffolded names and
counters are never hand-derived. Use
`zentaizo path effort [label]` to resolve an effort plan doc and `zentaizo path
slice <id>` for a slice file.

`brainstorming/` remains permissive: raw transcripts, sketches, and pasted
design documents from elsewhere may live there as freeform files. When a pre-decision
input should carry provenance and an `edited_by:` ledger, use
`zentaizo next-brainstorming <slug>` to scaffold
`sessions/brainstorming/YYYY-MM-DD-<slug>.md`.

`changes/` and `debugging/` slice frontmatter includes `short_title`, a
human/agent-authored title for compact session headers. The CLI can fill it via
`next-change --short-title` or `next-debugging --short-title`, but the field is
workspace intent: review it like the rest of the plan frontmatter. It is not
machine lock state and does not belong in `zentaizo.lock.json`. The CLI writes
the title as a double-quoted YAML string; a hand-written title may also be
plain or single-quoted.

Frontmatter-bearing session files (`efforts/`, generated `brainstorming/`, `changes/`, `debugging/`, `reports/`, `handoffs/`) also carry an `edited_by:` ledger recording which model or human crafted, reviewed, or modified the file, in order. The scaffolding commands stamp the first entry, and `zentaizo edited <path>` appends or refreshes it on later edits — resolving the editor identity from the same commit-trailer cache the commit-attribution hook uses, with a Codex config fallback that populates that cache when it is missing, so the recorded model + reasoning effort is never the model's own guess. Raw/freeform brainstorming dumps may not have frontmatter and are not required to support `zentaizo edited`.

These are useful for preserving the reasoning behind an answer or implementation plan.

## Skills

`skills/` holds plain-markdown procedures for any LLM-driven coding tool (Claude Code, Codex CLI, Gemini CLI, Aider, etc.). Each file describes one task. There is no YAML frontmatter and no tool-specific directory layout — discovery happens through `AGENTS.md`, which is the entrypoint every model-agnostic coding agent reads first.

Harnesses are wired to `AGENTS.md` per their own conventions. The generated `CLAUDE.md` is an `@AGENTS.md` import — Claude reads `CLAUDE.md`, not `AGENTS.md`, and loads the import in full at launch (a `SessionStart` hook would cap output at 10k characters, so the import is the reliable path); `GEMINI.md` remains a thin pointer.

The bundled `skills/curate-atlas.md` walks the agent through interviewing the user and populating `zentaizo.atlas.json`. It explicitly does not write to host-tool memory (CLAUDE.md, GEMINI.md, `.codex/`, `.aider.conf.yml`, etc.); the atlas describes the *system*, while those files describe the *user*.
