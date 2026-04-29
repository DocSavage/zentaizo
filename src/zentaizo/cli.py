from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

ATLAS_NAME = "zentaizo.atlas.json"
LEGACY_CONFIG_NAME = "zentaizo.config.json"
LOCK_NAME = "zentaizo.lock.json"
BEGIN_MARKER = "<!-- BEGIN zentaizo -->"
END_MARKER = "<!-- END zentaizo -->"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise SystemExit(f"Missing file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: pathlib.Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def default_atlas(name: str) -> dict:
    return {
        "version": 1,
        "name": name,
        "description": "A multi-source context workspace for an AI assistant.",
        "sources": {
            "repos": [
                {
                    "name": "shortener-api",
                    "url": "https://github.com/example/shortener-api.git",
                    "ref": "main",
                    "description": "REST API for creating and resolving short links",
                },
                {
                    "name": "shortener-web",
                    "url": "https://github.com/example/shortener-web.git",
                    "ref": "main",
                    "description": "Web UI for managing short links",
                },
                {
                    "name": "shortener-client",
                    "url": "https://github.com/example/shortener-client.git",
                    "ref": "main",
                    "description": "Client library used by scripts and integrations",
                },
            ],
            "docs": [
                {
                    "name": "api-docs",
                    "url": "https://example.com/shortener/api",
                    "description": "Public API documentation",
                }
            ],
            "papers": [],
            "notes": [],
        },
        "summaries": {
            "output_dir": "summaries",
            "levels": ["system", "source", "module"],
        },
    }


def initial_lock(name: str) -> dict:
    now = utc_now()
    return {
        "version": 1,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "sources": {
            "repos": [],
            "docs": [],
            "papers": [],
            "notes": [],
        },
    }


def workspace_readme(name: str) -> str:
    return f"""# {name}

This is a Zentaizo workspace: a local context atlas for an AI assistant.

## First Step

This workspace intentionally starts without `{ATLAS_NAME}`. The first useful interaction is to ask an AI assistant to help identify the repos, docs, papers, notes, deployment material, and issue context that belong in this atlas.

Example prompt:

> Use the Zentaizo instructions in `AGENTS.md` to interview me and draft `{ATLAS_NAME}` for this project. Do not write to assistant memory or global rule files.

## Workflow

```bash
# 1. Create the human-authored source atlas with AI assistance.
$EDITOR {ATLAS_NAME}

# 2. Check the source atlas shape.
zentaizo validate

# 3. Fetch source snapshots and update {LOCK_NAME}.
zentaizo fetch

# 4. Prepare hierarchical summaries.
zentaizo summarize

# 5. Give another repository access to this context.
zentaizo provide-info /path/to/repo-you-are-editing
```

## Consultation Order

When answering questions or making changes, start broad and drill down:

1. `summaries/`
2. `repos/`
3. `docs/`
4. `papers/`
5. `notes/`

Use `{LOCK_NAME}` to cite the exact source versions used for an answer.
"""


def workspace_agents(name: str) -> str:
    return f"""# Assistant Context

This directory is a Zentaizo workspace for `{name}`.

## First Task

If `{ATLAS_NAME}` is missing, make creating it the first task. Interview the user to identify the source material that defines this system, then draft `{ATLAS_NAME}` as the human-authored context atlas.

Use the `zentaizo` skill if it is available. If it is not available, follow this workflow directly:

1. Identify the system boundary: the product, service, research area, or ecosystem this workspace should explain.
2. List core repositories, including services, frontends, clients, SDKs, shared libraries, schemas, deployment, tests, and examples.
3. List durable docs, papers, specs, design notes, issue reports, traces, and local notes that future assistants should consult.
4. Separate core sources from useful background. Put unresolved relevance or version questions in `summaries/open-questions.md`.
5. Write `{ATLAS_NAME}` with explicit JSON: `version`, `name`, `description`, grouped `sources`, and summarization settings.

Do not write to Claude Memory, ChatGPT Memory, global Codex memory, IDE-wide rule stores, or other personal memory systems unless the user explicitly asks. Keep durable project context in this workspace as committed markdown, JSON, and lock files.

## Source Consultation

Use this order unless the user asks for something more specific:

1. Start with `summaries/` for the big picture.
2. Use `repos/` for implementation details.
3. Use `docs/` for public API or user-facing behavior.
4. Use `papers/` for design rationale.
5. Use `notes/` for traces, issue reports, and local decisions.

Prefer claims grounded in `zentaizo.lock.json` and source paths.
"""


def create_workspace(args: argparse.Namespace) -> int:
    target = pathlib.Path(args.path).resolve()
    name = args.name or target.name

    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"Target exists and is not empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    for subdir in [
        "repos",
        "docs",
        "papers",
        "notes",
        "summaries",
        "sessions/questions",
        "sessions/debugging",
        "sessions/changes",
    ]:
        (target / subdir).mkdir(parents=True, exist_ok=True)

    (target / "README.md").write_text(workspace_readme(name))
    (target / "AGENTS.md").write_text(workspace_agents(name))
    (target / ".gitignore").write_text(
        "\n".join(
            [
                "repos/",
                "docs/snapshots/",
                "papers/*.pdf",
                ".zentaizo/",
                "",
            ]
        )
    )

    print(f"Created Zentaizo workspace: {target}")
    print(f"Next: start an AI session in {target} to create {ATLAS_NAME}")
    return 0


def find_atlas(workspace: pathlib.Path) -> pathlib.Path | None:
    atlas = workspace / ATLAS_NAME
    if atlas.exists():
        return atlas

    legacy = workspace / LEGACY_CONFIG_NAME
    if legacy.exists():
        return legacy

    return None


def missing_atlas_message(workspace: pathlib.Path) -> str:
    return (
        f"Missing source atlas: {workspace / ATLAS_NAME}\n"
        f"Start an AI session in this workspace and ask it to help create {ATLAS_NAME} "
        "from the relevant repos, docs, papers, notes, and issue context."
    )


def load_workspace(path: str) -> tuple[pathlib.Path, dict]:
    workspace = pathlib.Path(path).resolve()
    atlas = find_atlas(workspace)
    if atlas is None:
        raise SystemExit(missing_atlas_message(workspace))

    config = read_json(atlas)
    return workspace, config


def source_groups(config: dict) -> dict:
    sources = config.get("sources")
    if isinstance(sources, dict):
        return sources
    return {
        "repos": config.get("repos", []),
        "docs": config.get("docs", []),
        "papers": config.get("papers", []),
        "notes": config.get("notes", []),
    }


def validate_workspace(args: argparse.Namespace) -> int:
    workspace = pathlib.Path(args.workspace).resolve()
    atlas = find_atlas(workspace)
    if atlas is None:
        print(f"{workspace}: invalid")
        print(f"- Missing source atlas: {ATLAS_NAME}")
        print(f"- First create {ATLAS_NAME} with AI assistance from this workspace.")
        return 1

    config = read_json(atlas)
    errors: list[str] = []
    sources = source_groups(config)

    if not config.get("name"):
        errors.append("Missing top-level name")

    for index, repo in enumerate(sources.get("repos", []), start=1):
        for field in ["name", "url", "ref"]:
            if not repo.get(field):
                errors.append(f"repos[{index}] is missing {field}")

    for group in ["docs", "papers", "notes"]:
        for index, item in enumerate(sources.get(group, []), start=1):
            if not item.get("name"):
                errors.append(f"{group}[{index}] is missing name")

    if errors:
        print(f"{workspace}: invalid")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"{workspace}: valid")
    print(f"Atlas: {atlas.name}")
    print_counts(sources)
    return 0


def print_counts(sources: dict) -> None:
    print(
        "Sources: "
        f"{len(sources.get('repos', []))} repos, "
        f"{len(sources.get('docs', []))} docs, "
        f"{len(sources.get('papers', []))} papers, "
        f"{len(sources.get('notes', []))} notes"
    )


def status_workspace(args: argparse.Namespace) -> int:
    workspace = pathlib.Path(args.workspace).resolve()
    atlas = find_atlas(workspace)
    if atlas is None:
        print(f"Workspace: {workspace.name}")
        print(f"Path: {workspace}")
        print(f"Atlas: missing {ATLAS_NAME}")
        print(f"Next: start an AI session here to create {ATLAS_NAME}.")
        lock_path = workspace / LOCK_NAME
        if lock_path.exists():
            lock = read_json(lock_path)
            print(f"Lock updated: {lock.get('updated_at', 'unknown')}")
        else:
            print(f"Lock: missing {LOCK_NAME}")
        return 0

    config = read_json(atlas)
    sources = source_groups(config)
    print(f"Workspace: {config.get('name', workspace.name)}")
    print(f"Path: {workspace}")
    print(f"Atlas: {atlas.name}")
    print_counts(sources)

    lock_path = workspace / LOCK_NAME
    if lock_path.exists():
        lock = read_json(lock_path)
        print(f"Lock updated: {lock.get('updated_at', 'unknown')}")
        print(f"Locked repos: {len(lock.get('sources', {}).get('repos', []))}")
    else:
        print(f"Lock: missing {LOCK_NAME}")
    return 0


def run_git(args: list[str], cwd: pathlib.Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def fetch_workspace(args: argparse.Namespace) -> int:
    workspace, config = load_workspace(args.workspace)
    sources = source_groups(config)
    repos = sources.get("repos", [])
    lock = read_json(workspace / LOCK_NAME) if (workspace / LOCK_NAME).exists() else initial_lock(config.get("name", workspace.name))
    locked_repos = []

    for repo in repos:
        name = repo["name"]
        dst = workspace / "repos" / name
        if not dst.exists():
            print(f"Cloning {name}...")
            run_git(["clone", repo["url"], str(dst)])
        else:
            print(f"Fetching {name}...")

        run_git(["fetch", "--tags", "--prune"], cwd=dst)
        run_git(["checkout", repo["ref"]], cwd=dst)
        commit = run_git(["rev-parse", "HEAD"], cwd=dst)
        dirty = bool(run_git(["status", "--porcelain"], cwd=dst))
        locked_repos.append(
            {
                "name": name,
                "url": repo["url"],
                "ref": repo["ref"],
                "commit": commit,
                "path": str(dst.relative_to(workspace)),
                "dirty": dirty,
                "fetched_at": utc_now(),
            }
        )
        print(f"Locked {name} @ {commit[:12]}")

    lock["updated_at"] = utc_now()
    lock.setdefault("sources", {})["repos"] = locked_repos
    lock["sources"]["docs"] = sources.get("docs", [])
    lock["sources"]["papers"] = sources.get("papers", [])
    lock["sources"]["notes"] = sources.get("notes", [])
    write_json(workspace / LOCK_NAME, lock)

    if sources.get("docs") or sources.get("papers"):
        print("Docs and papers are recorded in the lock file; snapshot download is a future command.")
    return 0


def summarize_workspace(args: argparse.Namespace) -> int:
    workspace, config = load_workspace(args.workspace)
    sources = source_groups(config)
    summaries_dir = workspace / config.get("summaries", {}).get("output_dir", "summaries")
    summaries_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = summaries_dir / "summarize.prompt.md"
    source_lines = []

    for group in ["repos", "docs", "papers", "notes"]:
        items = sources.get(group, [])
        if not items:
            continue
        source_lines.append(f"### {group}")
        for item in items:
            desc = f" - {item.get('description')}" if item.get("description") else ""
            source_lines.append(f"- `{item.get('name')}`{desc}")

    prompt_path.write_text(
        "\n".join(
            [
                "# Zentaizo Summary Task",
                "",
                "Produce hierarchical summaries for this workspace.",
                "",
                "Start with the big picture, then summarize each source at a useful level of detail.",
                "",
                "## Output Files",
                "",
                "- `summaries/overview.md`: system-level map",
                "- `summaries/sources/<name>.md`: one summary per source",
                "- `summaries/relationships.md`: how the sources interact",
                "- `summaries/open-questions.md`: gaps or assumptions",
                "",
                "## Sources",
                "",
                *source_lines,
                "",
                "Ground all claims in source paths or locked document metadata.",
            ]
        )
        + "\n"
    )
    print(f"Wrote summary prompt: {prompt_path}")
    print("Next: ask your assistant to follow that prompt from this workspace.")
    return 0


def build_reference_block(workspace: pathlib.Path, config: dict) -> str:
    name = config.get("name", workspace.name)
    atlas = find_atlas(workspace) or (workspace / ATLAS_NAME)
    return "\n".join(
        [
            BEGIN_MARKER,
            "## Zentaizo Context",
            "",
            f"This project can use the `{name}` Zentaizo workspace for broader system context:",
            "",
            f"- Workspace: `{workspace}`",
            f"- Atlas: `{atlas}`",
            f"- Summaries: `{workspace / 'summaries'}`",
            f"- Repositories: `{workspace / 'repos'}`",
            f"- Lockfile: `{workspace / LOCK_NAME}`",
            "",
            "When a task depends on related repos, docs, papers, or notes, start with the summaries and then drill into the locked sources.",
            END_MARKER,
            "",
        ]
    )


def inject_block(path: pathlib.Path, block: str) -> None:
    if path.exists():
        content = path.read_text()
        begin = content.find(BEGIN_MARKER)
        end = content.find(END_MARKER)
        if begin != -1 and end != -1:
            content = content[:begin] + block.rstrip() + content[end + len(END_MARKER):]
        else:
            content = content.rstrip() + "\n\n" + block
    else:
        content = "# Repository Guidelines\n\n" + block
    path.write_text(content.rstrip() + "\n")


def provide_info(args: argparse.Namespace) -> int:
    workspace, config = load_workspace(args.workspace)
    target = pathlib.Path(args.target).resolve()
    if not target.is_dir():
        raise SystemExit(f"Target directory does not exist: {target}")

    agents_path = target / "AGENTS.md"
    inject_block(agents_path, build_reference_block(workspace, config))
    print(f"Updated {agents_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zentaizo",
        description="Build hierarchical context workspaces for AI assistants.",
    )
    parser.add_argument("--version", action="version", version="zentaizo 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a new Zentaizo workspace")
    create.add_argument("path", help="workspace directory to create")
    create.add_argument("--name", help="display name for the workspace")
    create.set_defaults(func=create_workspace)

    validate = sub.add_parser("validate", help="validate a workspace atlas")
    validate.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    validate.set_defaults(func=validate_workspace)

    status = sub.add_parser("status", help="show workspace source and lock status")
    status.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    status.set_defaults(func=status_workspace)

    fetch = sub.add_parser("fetch", help="fetch repo snapshots and update the lock file")
    fetch.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    fetch.set_defaults(func=fetch_workspace)

    summarize = sub.add_parser("summarize", help="write a prompt for hierarchical summaries")
    summarize.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    summarize.set_defaults(func=summarize_workspace)

    provide = sub.add_parser("provide-info", help="inject Zentaizo context into another repo's AGENTS.md")
    provide.add_argument("target", help="target repository directory")
    provide.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    provide.set_defaults(func=provide_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
