# Repository Guidelines

This repository contains the Zentaizo CLI and workspace format.

## Goal

Keep the top-level experience simple: a developer should understand the problem, create a workspace, list sources, fetch snapshots, summarize them, and provide that context to an AI assistant.

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
