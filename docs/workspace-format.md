# Workspace Format

A Zentaizo workspace is a local context atlas for one broader system.

```text
my-system-atlas/
  AGENTS.md
  README.md
  zentaizo.atlas.json       # created after source discovery
  zentaizo.lock.json        # written by fetch

  repos/
  docs/
  papers/
  notes/
  summaries/
  graphify-out/             # derived knowledge graph (written by `zentaizo graph`)
  .graphifyignore           # managed graph-scoping file (regenerated per build)
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

Each `docs` entry may carry an optional `kind`, one of `api-reference`, `guide`, `tutorial`, `spec`, or `changelog`. It is used to order how an assistant consults docs (an `api-reference`/`spec` is the abbreviated layer between summaries and raw code) and is otherwise advisory.

A doc entry names its source one of two ways, never both:

- **External** — a `url` pointing at a documentation site (readthedocs/Sphinx/MkDocs, an `llms.txt`, an OpenAPI URL, etc.).
- **In-repo** — a `repo` (the `name` of a repo source in this atlas) plus a `path` relative to that repo's fetched tree, for an API definition that already ships in the code (e.g. an `openapi.yaml`). `validate` checks that the referenced repo exists and that a `path` is given; the file itself is resolved under `repos/<repo>/<path>` after `zentaizo fetch`, so it is not required to exist at validation time.

### Repo `role`

Each repo entry carries an optional `role` field. Two values are supported, with `reference` as the default when the field is omitted:

- `role: "edit"` — code the user will modify in this workspace. The `ref` is a starting point. `zentaizo fetch` clones and checks out `ref` only on the first fetch; after that it refreshes remotes and leaves the working tree alone, so branches and commits-in-progress survive future fetches. If the working tree is clean and HEAD is behind the upstream `ref`, `fetch` prints the rebase command; `zentaizo fetch --rebase` runs it.
- `role: "reference"` — code consulted but not changed. The `ref` is a pin. `zentaizo fetch` re-resolves it on every run (so `ref: main` tracks main; pin to a SHA or tag if you want stability) and refuses to overwrite a dirty working tree.

The split lets one workspace act like a coordinated mini-monorepo for related repos: editable ones mounted read-write into a sandbox, reference ones mounted read-only.

Use branches or tags while exploring. Use commits when you need a fully reproducible snapshot.

## `zentaizo.lock.json`

This file is machine-authored. It records what was actually fetched. It is written after a source atlas exists and `zentaizo fetch` resolves source versions.

For repositories, the lock file should include:

- source name
- URL
- requested ref
- resolved commit SHA
- local path
- dirty status
- fetch time

For docs and papers, future versions should record:

- source URL
- local snapshot path
- content hash
- fetch time
- conversion metadata, if HTML or PDF was converted for summarization

After `zentaizo graph` runs, the lock also carries a top-level `graph` block: the backend (`graphify`) and its version, the build `mode` (`code-only` or `semantic`, plus `semantic_backend`/`semantic_model` for the latter), `built_from` (each graphed source mapped to the locked identity it was built from), `not_graphed` (excluded sources mapped to reasons), and the safety verdict for `GRAPH_REPORT.md` (`report_status`). Staleness is a pure diff of `built_from` against the current lock, scoped to the recorded mode.

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

The assistant should read summaries before scanning source code.

## Graph

`graphify-out/` is the structural counterpart to `summaries/`: a queryable
knowledge graph over the whole workspace, built by `zentaizo graph` with
[Graphify](https://github.com/safishamsi/graphify) (optional tier — the
workspace works without it). Summaries are the prose level-of-detail spine;
the graph answers structural questions (`graphify query` / `path` /
`explain`), especially cross-repo relationships.

The whole directory is derived output and gitignored — `graph.json` alone can
sit near GitHub's 100 MiB per-file push limit on multi-repo workspaces, while
a cold rebuild costs about a minute of local compute (offline tree-sitter
extraction, no LLM tokens). Each clone rebuilds it locally: `zentaizo graph`
after `zentaizo fetch`.

```text
graphify-out/             # gitignored as a whole — rebuilt per clone
  graph.json              # machine-derived graph, like the lock but rebuildable
  GRAPH_REPORT.md         # markdown context, like a summary
  graph.html              # interactive visualization
  manifest.json           # build manifest (workspace-relative paths only)
  cache/                  # content-addressed extraction cache
  cost.json               # local-only run costs
```

The default build is code-only and fully offline; `zentaizo graph --semantic
--backend …` opts into model-API extraction of papers and notes. The managed
`.graphifyignore` at the workspace root scopes Graphify to the source trees
(it replaces the workspace `.gitignore` in Graphify's walk, which is what
makes the gitignored `repos/` graphable); it is deterministic output,
committed like the lock, and regenerated on every build. A flagged
`GRAPH_REPORT.md` is quarantined as `GRAPH_REPORT.flagged.md` — absence of
the report *is* the quarantine. Provenance and staleness live in the lock's
`graph` block (see above); `zentaizo status` reports them, and `zentaizo
fetch` keeps the code side of the graph fresh best-effort.

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
external planning docs may live there as freeform files. When a pre-decision
input should carry provenance and an `edited_by:` ledger, use
`zentaizo next-brainstorming <slug>` to scaffold
`sessions/brainstorming/YYYY-MM-DD-<slug>.md`.

`changes/` and `debugging/` slice frontmatter includes `short_title`, a
human/agent-authored title for compact session headers. The CLI can fill it via
`next-change --short-title` or `next-debugging --short-title`, but the field is
workspace intent: review it like the rest of the plan frontmatter. It is not
machine lock state and does not belong in `zentaizo.lock.json`.

Frontmatter-bearing session files (`efforts/`, generated `brainstorming/`, `changes/`, `debugging/`, `reports/`, `handoffs/`) also carry an `edited_by:` ledger recording which model or human crafted, reviewed, or modified the file, in order. The scaffolding commands stamp the first entry, and `zentaizo edited <path>` appends or refreshes it on later edits — resolving the editor identity from the same commit-trailer cache the commit-attribution hook uses, with a Codex config fallback that populates that cache when it is missing, so the recorded model + reasoning effort is never the model's own guess. Raw/freeform brainstorming dumps may not have frontmatter and are not required to support `zentaizo edited`.

These are useful for preserving the reasoning behind an answer or implementation plan.

## Skills

`skills/` holds plain-markdown procedures for any LLM-driven coding tool (Claude Code, Codex CLI, Gemini CLI, Aider, etc.). Each file describes one task. There is no YAML frontmatter and no tool-specific directory layout — discovery happens through `AGENTS.md`, which is the entrypoint every model-agnostic coding assistant reads first.

Host tools are wired to `AGENTS.md` per their own conventions. The generated `CLAUDE.md` is an `@AGENTS.md` import — Claude reads `CLAUDE.md`, not `AGENTS.md`, and loads the import in full at launch (a `SessionStart` hook would cap output at 10k characters, so the import is the reliable path); `GEMINI.md` remains a thin pointer.

The bundled `skills/curate-atlas.md` walks the assistant through interviewing the user and populating `zentaizo.atlas.json`. It explicitly does not write to host-tool memory (CLAUDE.md, GEMINI.md, `.codex/`, `.aider.conf.yml`, etc.); the atlas describes the *system*, while those files describe the *user*.
