# CLI Design

Zentaizo should feel like a normal tool:

```bash
zentaizo create my-system-atlas
zentaizo fetch
zentaizo summarize
zentaizo provide-info /path/to/repo
```

Pixi is useful for developing Zentaizo itself, but it should not be required in user-facing examples.

## How `zentaizo ...` Works

The Python package declares a console script in `pyproject.toml`:

```toml
[project.scripts]
zentaizo = "zentaizo.cli:main"
```

After installation, Python creates a command named `zentaizo` that calls `zentaizo.cli:main`.

For development:

```bash
python -m pip install -e .
zentaizo --help
```

For isolated local use:

```bash
pipx install -e .
zentaizo --help
```

With Pixi:

```bash
pixi install
pixi run install-cli
zentaizo --help
```

The design rule is that `zentaizo` is the product interface. `python -m zentaizo`, `pipx`, and `pixi` are bootstrap paths.

## Initial Commands

```bash
zentaizo create PATH
```

Creates a workspace shell with source directories, summaries directory, and assistant instructions. It does not create `zentaizo.atlas.json`; the first AI-assisted setup step is to identify the source material and create that human-authored atlas.

```bash
zentaizo validate [PATH]
```

Checks that `zentaizo.atlas.json` exists and has the required shape. Legacy `zentaizo.config.json` workspaces are still readable.

```bash
zentaizo status [PATH]
```

Shows source counts and lock status. If the atlas is missing, shows the setup prompt instead of failing.

```bash
zentaizo fetch [PATH]
```

Fetches repositories listed in `zentaizo.atlas.json` and records exact commits in `zentaizo.lock.json`.

```bash
zentaizo summarize [PATH]
```

Writes a prompt for hierarchical summarization. A later version can run a configured LLM directly.

```bash
zentaizo provide-info TARGET [PATH]
```

Adds a Zentaizo reference block to `TARGET/AGENTS.md` so an assistant working in that repository knows where to look.
