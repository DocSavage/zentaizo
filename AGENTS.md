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
