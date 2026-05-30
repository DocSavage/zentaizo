# Zentaizo

Zentaizo helps an AI agent understand the big picture of a complex system before it dives into source code. It's a tool that can create an AI-native workspace: a virtual monorepo for a curated set of repos, papers, API docs, etc. When installed as a shared skill among your chosen AI harnesses, it also serves as a way to share curated, git-persisted, hierarchically-scaled information.

The name comes from Japanese `zentaizo` (`全体像`, usually romanized `zentaizō`), meaning the overall picture.

## Why This Exists

Useful software work often depends on context that lives outside the repository you are editing:

- related service repositories
- web frontends and client libraries
- deployment configuration
- public documentation
- design docs and papers
- issue reports, traces, and local notes

An agent can answer better questions and make better changes when it has a structured way to see that broader context. Zentaizo is a workspace format and command-line tool for building that curated context in a token-efficient readable way.

Aside from external information, zentaizo provides a shared skill for where to share git-persisted information during planning, analysis, and implementation.

## Core Ideas

- Big picture first: facilitate human-guided documentation of the whole landscape of a system, so an agent understands it before diving into source.
- Level of detail: keep summaries at different scales, from system overview to source files, drilling into specifics only when necessary.
- Heterogeneous sources: include repos, docs, papers, notes, issue reports, and generated analysis.
- Multi-repo sandbox: the agent's working set is not one repo but associated repos, similar to a monorepo's utility for coherent, cross-system development.
  - Edit vs reference: each repo declares whether it is editable in this workspace (`role: "edit"`) or read-only context (`role: "reference"`). `zentaizo fetch` honors the split — edit repos keep their working tree across fetches, reference repos re-resolve their pins. The split also drives sandbox isolation: editable repos can be mounted read-write into an AI-friendly container, reference repos read-only.
- Reproducibility and determinism as a first-class value: AI-assisted work should be auditable and repeatable, not a one-off that the next session — or a different model — can't reconstruct. Implemented two ways:
  - Pinned sources: repos and document snapshots resolve to exact commits and content hashes (recorded in `zentaizo.lock.json`), so the context behind an answer or change can be reproduced later.
  - Deterministic tooling over model instructions: mechanical, single-correct-answer work (session-file allocation, counter and path resolution, frontmatter) lives in the CLI, not in prose the model re-derives each session. Minimizing model-side instructions removes a class of behavior that drifts and rots with context.
- Model-agnostic: the workspace is the source of truth, not any one assistant. `AGENTS.md` holds the model-neutral instructions, `CLAUDE.md`/`GEMINI.md` stay thin pointers to it, and the shared skill installs across Claude, Codex, and Gemini.
- Human-curated context: the atlas (`zentaizo.atlas.json`) is human-authored intent — the curated engine of the workspace — while lock files record machine-resolved state. Zentaizo builds scaffolding for human + AI collaboration, not an autonomous agent.

## A Small Example

Imagine a small URL shortener split across several repositories:

- `shortener-api`: REST API for creating and resolving short links
- `shortener-web`: web UI for managing links
- `shortener-client`: Python or JavaScript client library
- `deployment`: Docker, Helm, or Terraform configuration
- public API docs

You want to ask:

> If we add link expiration, which repos need to change, and what contract should they share?

Zentaizo is meant to prepare the agent to answer that first, then help make the actual edits in the right repositories.

## How to Use

To install the zentaizo skill, which describes the workflow and conventions:

```bash
zentaizo skills install --target claude  # or codex, gemini, all
```

Typically you'd create a `zen-` prefixed workspace repo that targets a particular project where one or more of the fetched or created repos will be modified:

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

Then, from `/path/to/shortener-api`, you can ask an AI agent:

> Using the Zentaizo context, inspect the related frontend and client library before changing the API contract for link expiration.

To seed a fresh workspace from an existing one that overlaps in scope (same
repos pinned, same papers, shared design notes), use `seed-from`:

```bash
zentaizo seed-from ../zen-old-workspace            # prompts per atlas entry
zentaizo seed-from ../zen-old-workspace --dry-run  # preview without writing
zentaizo seed-from ../zen-old-workspace --accept-all
```

It walks the source atlas, asks per repo/doc/paper/note (or skips prompts with
`--accept-all`), appends accepted entries to the target atlas, and copies any
local files referenced by `path:` (typical for notes). Repos are re-pinned
declaratively in the atlas; the working tree is populated by `zentaizo fetch`
afterward, not by copying `repos/`. Existing target atlas entries with the same
name are left untouched.

To bring an older workspace forward when Zentaizo's conventions have changed,
run an AI session in the workspace and point it at the experimental
`upgrade-zentaizo` procedure bundled in the global Zentaizo skill. It diffs the
current templates against the workspace, classifies each delta, and plans any
artifact migrations (session-file frontmatter, filename conventions) before
making changes.

## Installing The Command

Develop on zentaizo (editable install in a pixi env):

```bash
pixi install                # bootstrap dev env
pixi run zentaizo --help
pixi run check              # ruff lint + tests
pixi run hooks-install      # one-time: enable pre-commit on `git commit`
```

Install for use across other projects (puts `zentaizo` on your `PATH`):

```bash
pipx install -e /path/to/zentaizo
zentaizo --help
```

If you don't have `pipx`: `pixi global install pipx` (or `brew install pipx`, `apt install pipx`).

Release (when ready): `pixi run build` then `pixi run publish`.

## What A Workspace Contains

After source discovery and fetch, a workspace looks like:

```text
zen-link-shortener/
  zentaizo.atlas.json       # human-authored context atlas, created after source discovery
  zentaizo.lock.json        # resolved commits, hashes, and snapshot metadata, written by fetch
  AGENTS.md                 # agent instructions for this context

  repos/                    # fetched source repositories
  docs/                     # documentation snapshots
  papers/                   # PDFs and specs
  notes/                    # issue reports, traces, design notes
  summaries/                # generated hierarchical summaries
  skills/                   # model-agnostic procedures (curate-atlas, plan-*, report-template)
  sessions/
    efforts.json            # effort registry: labels, current pointer, repo/branch map
    brainstorming/          # pre-decision input: AI discussions, sketches, source inventories
    changes/                # implementation plans (slices), amended with outcomes
    debugging/              # bug investigations: traces, hypotheses, root cause
    questions/              # dated Q&A logs with researched answers and citations
    handoffs/               # paste-ready execution prompts for the implementing agent
    reports/                # living evidence-backed syntheses (must-read deliverables)
```

## Safety

A workspace deliberately aggregates external material — fetched repositories, documentation, notes, and papers — for an AI assistant to read. Treat all of it as **untrusted input**: content pulled from the web or third-party repos can carry indirect prompt-injection payloads (hidden instructions, fake system messages, invisible characters). The generated workspace `AGENTS.md` instructs assistants to read this material as evidence to cite and summarize, **never as instructions to follow**. Hardened fetch-time handling — sanitization, quarantine, and a summarize-as-quarantine-boundary pattern — is planned; see `docs/design/api-reference-docs-layer.md` (§2.9).

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
6. When Zentaizo's conventions move forward, use the experimental `upgrade-zentaizo` skill in an AI session to reconcile the workspace.

See `docs/` for the initial design notes.
