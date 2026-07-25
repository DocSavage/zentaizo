---
name: zentaizo
description: Build and maintain Zentaizo context workspaces for AI-assisted work across related repositories, docs, papers, notes, and generated markdown summaries. Use when creating or revising a Zentaizo workspace, deciding what belongs in the human-authored context atlas zentaizo.atlas.json, preparing markdown context to commit for future assistant use, injecting Zentaizo context into another repo, or avoiding conflicts with Claude Memory, AGENTS.md, CLAUDE.md, ChatGPT Memory, Cursor rules, or other assistant memory/instruction systems.
---

# Zentaizo

> **First, check where you are.** If the working directory is the **Zentaizo
> tool repo itself** — you will see `src/zentaizo/`, `pyproject.toml`, and a
> `src/zentaizo/templates/` directory — then you are *developing* Zentaizo, not
> using a workspace. This skill describes how to *use* a workspace; do **not**
> follow it as a workflow there. Read that repo's `AGENTS.md` instead. The rest
> of this skill assumes you are inside a Zentaizo workspace (it has
> `zentaizo.atlas.json` or an `AGENTS.md` that names itself a Zentaizo
> workspace).

## Overview

Use Zentaizo as a project-local context atlas, not as a replacement for an assistant's memory system. Help the user identify sources that define a system's goals/architecture/implementation, and turn that real-world knowledge into committed markdown and, crucially, the human-curated context atlas (`zentaizo.atlas.json`).

Call `zentaizo.atlas.json` the "context atlas" so the user understands its role as the curated engine of the workspace.

## Workflow

1. Orient on the workspace.
   - Read `README.md`, `AGENTS.md`, `docs/`, the current context atlas if present, and any lock file before making recommendations.
   - The workspace's own `AGENTS.md` is authoritative for workspace conventions (filenames, frontmatter, sessions/ workflow). When it disagrees with anything written below, follow the workspace `AGENTS.md`.
   - `zentaizo setup --check` is the read-only way to inspect global skill and tool availability. Run the mutating `zentaizo setup` only after the user explicitly authorizes it.
   - If `zentaizo.atlas.json` is missing, treat creating it as the first task.
   - Ask only for the minimum missing facts needed to identify the system boundary.
   - Prefer concrete examples and existing repo conventions over abstract taxonomy.

2. Define the system boundary.
   - Identify the product, service, research area, or ecosystem the workspace is meant to explain.
   - Separate core sources from useful background. Core sources are needed to answer likely Q&A, debugging, design, or implementation questions.
   - Mark unclear ownership, version, or relevance as an open question instead of guessing.

3. Inventory sources.
   - Include repositories for services, clients, SDKs, frontends, deployment, schemas, tests, examples, and shared libraries.
   - Include docs for public APIs, internal runbooks, specs, design docs, architecture records, changelogs, and issue reports.
   - Include papers or standards when they explain domain concepts or design rationale that code alone will not reveal.
   - Include notes for traces, incidents, reproduction steps, user reports, local decisions, and curated explanations.
   - Exclude personal preferences, secrets, credentials, private memory snippets, and ephemeral chat unless they are distilled into a durable note.

4. Draft or revise `zentaizo.atlas.json`.
   - Keep JSON explicit and boring: `version`, `name`, `description`, grouped `sources`, and summarization settings.
   - Give every source a stable `name`, a fetchable `url` or local path, and a concise `description` of why it matters.
   - Use branches or tags while exploring. Prefer commits when an answer, benchmark, incident, or design depends on reproducibility.
   - Preserve human intent in the manifest. Let lock files record resolved commits, hashes, timestamps, and fetch metadata.

5. Prepare committed markdown context.
   - Build the workspace knowledge graph with `zentaizo graph` as a standard part of context prep (code-only and offline by default; it degrades gracefully when the `graphify` binary is absent). Answer structural and cross-repo questions with `graphify query` / `path` / `explain` instead of re-scanning sources; `graphify-out/` is derived output, rebuilt per clone with `zentaizo graph` after `zentaizo fetch`.
   - Write or update `summaries/overview.md` for the system map.
   - Write or update `summaries/relationships.md` for cross-source contracts and data flow, grounding claims in graph queries when the graph exists.
   - Write or update `summaries/open-questions.md` for gaps, assumptions, and follow-up discovery.
   - Write source-specific summaries under `summaries/sources/` when a source is important enough that future sessions should start with a compressed view.
   - Put incidents, traces, debugging records, and design notes under `notes/` or `sessions/` according to workspace convention.
   - Ground durable claims in source paths, URLs, locked versions, or explicit user-provided context.

6. Validate and hand off.
   - Run `zentaizo validate`, `zentaizo status`, and fetch, graph, or summarize commands when available and relevant.
   - Use `zentaizo provide-info TARGET` to add bounded Zentaizo instructions to another repo.
   - Explain the intended consultation order: summaries first, the knowledge graph for structural questions, then locked repos/docs/papers/notes as needed.

7. Allocate session files through the CLI — never hand-derive a name or counter.
   - Group work into an **effort** (a named body of work that may span several editable repos): `zentaizo effort new <word> --describe "…" --repo <name>=<branch>`; this also scaffolds `sessions/efforts/NNNN-<label>.md`, the effort-level plan doc. Inspect with `zentaizo effort list` / `zentaizo effort show`; resolve the doc with `zentaizo path effort [label]`.
   - Create files with `zentaizo next-change` / `next-debugging` / `next-handoff` / `next-note` / `next-report`; they default to the current effort and scaffold correct frontmatter.
   - Read with `zentaizo path slice <id>` (recovers the slug) and `zentaizo path active`. The workspace `AGENTS.md` § Filename Convention is authoritative for the details.

## Upgrading an existing workspace (experimental)

When the user asks to bring an older workspace forward to current Zentaizo
conventions — or when the workspace's bundled files have visibly fallen behind
the templates — read `upgrade-zentaizo.md` (sibling file in this skill folder)
and follow it. The procedure is deliberately AI-driven rather than CLI-driven
because convention changes routinely touch session-file frontmatter, filenames,
and cross-references. Treat each upgrade as a reviewable migration staged
through a normal `sessions/changes/` plan, not a one-shot rewrite.

## Reporting Zentaizo Tool Issues

When work in any Zentaizo workspace surfaces a bug, friction, or an improvement idea in the tool or its workspace conventions themselves, the set procedure is a GitHub issue on the tool's tracker: `gh issue create -R DocSavage/zentaizo`, citing the workspace, the exact command, expected vs. actual behavior. Confirm with the user before filing (it posts publicly); if `gh` is unavailable or the user prefers not to post, record the details in that workspace's `sessions/` (e.g. a brainstorming note) so it can be filed later. Do not silently work around tool problems.

## User Interview

Use these prompts when the source set is not obvious:

- What is the system or ecosystem this atlas should explain?
- Which repo would a developer usually edit first, and which repos does it depend on?
- Which frontend, SDK, CLI, deployment, schema, or docs must stay compatible with that repo?
- What questions should a future assistant answer better after reading this workspace?
- Are there incidents, traces, issue links, papers, or design notes that explain behavior not obvious from code?
- Which sources must be pinned to exact versions, and which can track a branch while exploring?

## Memory And Instruction Boundaries

Avoid conflicts with assistant memory systems:

- Do not write to Claude Memory, ChatGPT Memory, user-level custom instructions, global Codex memory, or IDE-wide rule stores unless the user explicitly asks.
- Keep durable project knowledge in the Zentaizo workspace as markdown, JSON, and lock files.
- Keep model-specific files thin. Prefer `AGENTS.md` for model-agnostic repository instructions. Let `CLAUDE.md` point to `AGENTS.md` unless Claude-specific behavior is truly required.
- When injecting into a target repo, use bounded marker blocks and preserve existing instructions outside those blocks.
- Treat memory and custom-instruction systems as personal or environment-level behavior. Treat Zentaizo as reproducible, reviewable, project-level context.
- Never store secrets, credentials, personal data, or unreviewed private chat transcripts in committed Zentaizo context.
