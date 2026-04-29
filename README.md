# Zentaizo

Zentaizo helps an AI assistant understand the big picture of a complex system before it dives into source code.

The name comes from Japanese `zentaizo` (`全体像`, usually romanized `zentaizō`), meaning the overall picture.

## Why This Exists

Useful software work often depends on context that lives outside the repository you are editing:

- related service repositories
- web frontends and client libraries
- deployment configuration
- public documentation
- design docs and papers
- issue reports, traces, and local notes

An assistant can answer better questions and make better changes when it has a structured way to see that broader context. Zentaizo is a workspace format and command-line tool for building that context in a token-efficient way.

## Core Ideas

- Big picture: facilitate human-guided documentation of the whole landscape of a system. 
- Level of detail: keep summaries at different scales, from system overview to source files, drilling into specifics only when necessary.
- Heterogeneous sources: include repos, docs, papers, notes, issue reports, and generated analysis.
- Pinning associated repos: the LLM sandbox is not just one repos but associated repos, similar to a monorepo's utility for coherent, cross-system development.

## A Small Example

Imagine a small URL shortener split across several repositories:

- `shortener-api`: REST API for creating and resolving short links
- `shortener-web`: web UI for managing links
- `shortener-client`: Python or JavaScript client library
- `deployment`: Docker, Helm, or Terraform configuration
- public API docs

You want to ask:

> If we add link expiration, which repos need to change, and what contract should they share?

Zentaizo is meant to prepare the assistant to answer that first, then help make the actual edits in the right repositories.

## Command Shape

The intended day-to-day interface is a normal command named `zentaizo`:

```bash
zentaizo create zen-link-shortener
cd zen-link-shortener

# Collaborate with your chosen LLM to identify the source material.
# The generated AGENTS.md explains that the first task is to create zentaizo.atlas.json.
# Ask: "Use the Zentaizo instructions here to interview me and draft zentaizo.atlas.json."

# Check the atlas shape.
zentaizo validate

# Fetch pinned source snapshots and write zentaizo.lock.json.
zentaizo fetch

# Prepare hierarchical summary prompts and outputs.
zentaizo summarize

# Give another repo instructions for using this context.
zentaizo provide-info /path/to/shortener-api
```

Then, from `/path/to/shortener-api`, you can ask an AI assistant:

> Using the Zentaizo context, inspect the related frontend and client library before changing the API contract for link expiration.

## Installing The Command

This repo exposes `zentaizo` through a standard Python console script:

```bash
python -m pip install -e .
zentaizo --help
```

For an isolated user install:

```bash
pipx install -e .
zentaizo --help
```

If you prefer `pixi`:

```bash
pixi install
pixi run install-cli
zentaizo --help
```

## What A Workspace Contains

After source discovery and fetch, a workspace looks like:

```text
zen-link-shortener/
  zentaizo.atlas.json       # human-authored context atlas, created after source discovery
  zentaizo.lock.json        # resolved commits, hashes, and snapshot metadata, written by fetch
  AGENTS.md                 # assistant instructions for this context

  repos/                    # fetched source repositories
  docs/                     # documentation snapshots
  papers/                   # PDFs and specs
  notes/                    # issue reports, traces, design notes
  summaries/                # generated hierarchical summaries
  sessions/                 # Q&A, debugging, and planning
```

## Use Cases

- Q&A across a system: answer how multiple repos and docs fit together.
- Debugging: trace an error through the service, client, deployment, and docs.
- Integrated design: plan a change that affects several repos before editing one.
- Implementation support: help an assistant modify the repo you are in while checking related repos for contracts and expectations, or handle a coherent multi-repo modification.
- Reproducible context: pin the exact commits and document snapshots used for an answer.

## Status

This is a starter repository. The first useful milestone is a simple local workflow:

1. Create a workspace.
2. Use the workspace `AGENTS.md` and Zentaizo skill to identify sources and create `zentaizo.atlas.json`.
3. Fetch repositories and write `zentaizo.lock.json`.
4. Generate or prepare hierarchical summaries.
5. Inject context instructions into a target repo.

See `docs/` for the initial design notes.
