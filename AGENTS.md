# Repository Guidelines

This repository contains the Zentaizo CLI and workspace format.

## Goal

Keep the top-level experience simple: a developer should understand the problem, create a workspace, list sources, fetch snapshots, summarize them, and provide that context to an AI assistant.

## Working in This Repo

This is the **Zentaizo tool repo** — the CLI and workspace *format*. zentaizo is
developed by **dogfooding**: the canonical checkout is an `edit` clone vendored
inside a `zen-zentaizo` workspace (the same kind the tool creates). That
workspace's root holds the full design provenance — `zentaizo.atlas.json`, the
`sessions/` trail, and `summaries/`. **This repo's tracked content never holds
those workspace artifacts** (`repos/` is gitignored by the workspace, so the two
git histories never cross); it carries the CLI, reference docs, and *distilled*
design docs. The global Zentaizo skill explains how to *use* a workspace — when
working inside `zen-zentaizo`, follow those workspace conventions; this repo is
the edit target.

**Distillation.** Settled design is promoted from the workspace trail into this
repo as distilled, repo-scoped docs (`docs/design/`) — architecture and rationale
generalized to author-level decisions, not conversational provenance.

**Bootstrapping.** The code under development *is* `repos/zentaizo` inside the
workspace, so run `zentaizo` workspace-bookkeeping through a **stable runner**
whose `import zentaizo` resolves *outside* `repos/zentaizo` (a non-editable
install), pointing each command at the workspace; exercise the dev build only
against throwaway `/tmp` workspaces.

Layout:

- `src/zentaizo/cli.py` — the CLI. The text generated *into* a workspace (its
  `AGENTS.md`, `README.md`, the `provide-info` block) lives here as functions
  (e.g. `workspace_agents()`), so changing a workspace convention is a code
  change here.
- `src/zentaizo/templates/` — files copied or installed into workspaces:
  - `global-skills/zentaizo/` — the global skill (`SKILL.md`,
    `upgrade-zentaizo.md`) installed by `zentaizo skills install`.
  - `skills/` — per-workspace skill templates (`curate-atlas`,
    `plan-and-implement`, `plan-template`, `effort-template`,
    `handoff-template`, `report-template`).
  - `hooks/prepare-commit-msg` — the commit-attribution hook bundled into
    workspaces.
- `docs/` — reference + distilled design. `docs/cli.md`,
  `docs/workspace-format.md`, and `docs/use-cases.md` are the contributor-facing
  reference docs; `docs/design/` holds distilled architecture + rationale. The
  before/after design *provenance* lives in the `zen-zentaizo` workspace's
  `sessions/` trail (brainstorming + effort/slice plans), not here.
- `tests/`, `examples/`.

Conventions:

- Capture new design work in the workspace `sessions/` trail (brainstorming →
  effort/slice plans), not as docs in this repo; promote the settled result here
  as a distilled `docs/design/` doc.
- Dev loop: `pixi install`, then `pixi run zentaizo --help` and `pixi run check`
  (ruff lint + tests). `pixi run hooks-install` enables the pre-commit
  attribution hook.
- The workspace model you are building, in one breath: a human-authored atlas
  (`zentaizo.atlas.json`) versus a machine-resolved lock; work grouped into
  *efforts* that decompose into *slice* plans under `sessions/`; the CLI
  allocates every session filename. The authoritative descriptions are
  `docs/workspace-format.md` and the `workspace_agents()` string in `cli.py`.

## Commands

```bash
python -m zentaizo --help
python -m zentaizo create /tmp/example-atlas
python -m zentaizo status /tmp/example-atlas
# After creating /tmp/example-atlas/zentaizo.atlas.json:
python -m zentaizo validate /tmp/example-atlas
```

To bring an older workspace forward after a Zentaizo conventions bump, run an
AI session in that workspace and use the experimental `upgrade-zentaizo`
skill (bundled in the global Zentaizo skill via `zentaizo skills install`).
There is no `zentaizo update` command — convention changes routinely touch
session-file frontmatter, filenames, and cross-references, and that
reconciliation is delegated to an AI-driven plan rather than a one-shot CLI
overwrite.

After editable installation:

```bash
zentaizo --help
```

## Style

- Keep README-level explanations short and example-driven.
- Put detailed design material in `docs/`.
- Treat `zentaizo.atlas.json` as human-authored intent.
- Treat `zentaizo.lock.json` as machine-authored resolved state.
- Prefer explicit, boring JSON over clever configuration syntax.
- Do not require Pixi for normal end-user command examples.
