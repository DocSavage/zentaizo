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
  sessions/
    efforts.json            # effort registry (seeded with numbered `main`)
    efforts/                # effort-level plan docs
  skills/
    curate-atlas.md         # model-agnostic interview procedure
    plan-and-implement.md   # the plan -> execute -> close-out lifecycle
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

## Sessions

Sessions are the durable trail of how the workspace has been used:

```text
sessions/
  efforts.json     # registry: effort labels, numbers, current pointer, per-repo branch/base
  efforts/         # effort-level plan docs
  brainstorming/   # pre-decision input (no schema)
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
`next-note` / `next-report` — so names and counters are never hand-derived. Use
`zentaizo path effort [label]` to resolve an effort plan doc and `zentaizo path
slice <id>` for a slice file.

Frontmatter-bearing session files (`efforts/`, `changes/`, `debugging/`, `reports/`, `handoffs/`) also carry an `edited_by:` ledger recording which model or human crafted, reviewed, or modified the file, in order. The scaffolding commands stamp the first entry, and `zentaizo edited <path>` appends or refreshes it on later edits — resolving the editor identity from the same commit-trailer cache the commit-attribution hook uses, so the recorded model + reasoning effort is never the model's own guess.

These are useful for preserving the reasoning behind an answer or implementation plan.

## Skills

`skills/` holds plain-markdown procedures for any LLM-driven coding tool (Claude Code, Codex CLI, Gemini CLI, Aider, etc.). Each file describes one task. There is no YAML frontmatter and no tool-specific directory layout — discovery happens through `AGENTS.md`, which is the entrypoint every model-agnostic coding assistant reads first.

The bundled `skills/curate-atlas.md` walks the assistant through interviewing the user and populating `zentaizo.atlas.json`. It explicitly does not write to host-tool memory (CLAUDE.md, GEMINI.md, `.codex/`, `.aider.conf.yml`, etc.); the atlas describes the *system*, while those files describe the *user*.
