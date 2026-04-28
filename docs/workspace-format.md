# Workspace Format

A Zentaizo workspace is a local context atlas for one broader system.

```text
my-system-atlas/
  zentaizo.config.json
  zentaizo.lock.json
  AGENTS.md
  README.md

  repos/
  docs/
  papers/
  notes/
  summaries/
  sessions/
```

## `zentaizo.config.json`

This file is human-authored. It says which sources belong to the system.

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

This file is machine-authored. It records what was actually fetched.

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
