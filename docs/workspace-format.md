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
  skills/
    curate-atlas.md         # model-agnostic interview procedure
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

Sessions are scratchpads for task-specific analysis:

```text
sessions/
  questions/
  debugging/
  changes/
```

These are useful for preserving the reasoning behind an answer or implementation plan.

## Skills

`skills/` holds plain-markdown procedures for any LLM-driven coding tool (Claude Code, Codex CLI, Gemini CLI, Aider, etc.). Each file describes one task. There is no YAML frontmatter and no tool-specific directory layout — discovery happens through `AGENTS.md`, which is the entrypoint every model-agnostic coding assistant reads first.

The bundled `skills/curate-atlas.md` walks the assistant through interviewing the user and populating `zentaizo.atlas.json`. It explicitly does not write to host-tool memory (CLAUDE.md, GEMINI.md, `.codex/`, `.aider.conf.yml`, etc.); the atlas describes the *system*, while those files describe the *user*.
