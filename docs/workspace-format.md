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

This file is human-authored. It says which sources belong to the system and why they matter.

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
        "description": "REST API for creating and resolving short links"
      }
    ],
    "docs": [
      {
        "name": "api-docs",
        "url": "https://example.com/shortener/api",
        "description": "Public API documentation"
      }
    ],
    "papers": [],
    "notes": []
  }
}
```

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
