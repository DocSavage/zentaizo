from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from importlib import resources

ATLAS_NAME = "zentaizo.atlas.json"
LEGACY_CONFIG_NAME = "zentaizo.config.json"
LOCK_NAME = "zentaizo.lock.json"
BEGIN_MARKER = "<!-- BEGIN zentaizo -->"
END_MARKER = "<!-- END zentaizo -->"

VALID_ROLES = ("edit", "reference")
DEFAULT_ROLE = "reference"


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
                    "role": "edit",
                    "description": "REST API for creating and resolving short links",
                },
                {
                    "name": "shortener-web",
                    "url": "https://github.com/example/shortener-web.git",
                    "ref": "main",
                    "role": "reference",
                    "description": "Web UI for managing short links",
                },
                {
                    "name": "shortener-client",
                    "url": "https://github.com/example/shortener-client.git",
                    "ref": "main",
                    "role": "reference",
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

> Use the Zentaizo instructions in `AGENTS.md` and the procedure in `skills/curate-atlas.md` to interview me and draft `{ATLAS_NAME}` for this project. Do not write to assistant memory or global rule files.

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

Read `skills/curate-atlas.md` for the full interview procedure and follow it. (If your host tool also exposes a `zentaizo` or `curate-atlas` skill, that skill loads the same file.) If `skills/curate-atlas.md` is missing, follow this workflow directly:

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

## Recording Work in `sessions/`

`sessions/` is the durable trail of how this workspace has been used. Prefer writing to it over leaving substantive work only in chat history. Three subdirectories already exist:

- `sessions/questions/` — Q&A logs. When the user asks a substantive cross-repo question and you produce a researched answer, save the question, the answer, and source citations as `sessions/questions/YYYY-MM-DD-<slug>.md`.
- `sessions/debugging/` — traces, hypotheses, and resolutions. When investigating a bug across the atlas, save the trace and final root cause as `sessions/debugging/YYYY-MM-DD-<slug>.md`.
- `sessions/changes/` — implementation plans for multi-repo changes. Before editing in earnest, save the plan (problem, files involved, step-by-step approach, verification) as `sessions/changes/YYYY-MM-DD-<slug>.md` so future sessions can resume from the same plan.

Filenames should sort chronologically. The slug should be 2–5 hyphenated words describing the topic (`shortener-link-expiration-contract`, not `plan1`).
"""


def install_skills_into_workspace(target: pathlib.Path) -> list[str]:
    """Copy the bundled model-agnostic skill files into <target>/skills/.

    Returns the list of skill filenames installed.
    """
    src = resources.files("zentaizo").joinpath("templates/skills")
    dst = target / "skills"
    dst.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    for entry in src.iterdir():
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue
        with resources.as_file(entry) as src_path:
            shutil.copy2(src_path, dst / entry.name)
        installed.append(entry.name)
    return installed


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

    if not getattr(args, "no_skills", False):
        installed = install_skills_into_workspace(target)
        if installed:
            print(f"Installed skills: {', '.join(sorted(installed))}")

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


def repo_role(repo: dict) -> str:
    """Return the role for a repo entry, normalized to a known value."""
    role = repo.get("role")
    if role in VALID_ROLES:
        return role
    return DEFAULT_ROLE


def count_roles(repos: list[dict]) -> tuple[int, int]:
    """Return (edit_count, reference_count) across the given repo list."""
    edit_count = sum(1 for repo in repos if repo_role(repo) == "edit")
    return edit_count, len(repos) - edit_count


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
        if "role" in repo and repo["role"] not in VALID_ROLES:
            allowed = ", ".join(repr(r) for r in VALID_ROLES)
            errors.append(
                f"repos[{index}] has invalid role {repo['role']!r}; expected one of {allowed}"
            )

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
    repos = sources.get("repos", [])
    edit_count, ref_count = count_roles(repos)
    repo_part = f"{len(repos)} repos"
    if repos:
        repo_part += f" ({edit_count} edit, {ref_count} reference)"
    print(
        "Sources: "
        f"{repo_part}, "
        f"{len(sources.get('docs', []))} docs, "
        f"{len(sources.get('papers', []))} papers, "
        f"{len(sources.get('notes', []))} notes"
    )


def _locked_repo_index(lock: dict) -> dict[str, dict]:
    return {entry.get("name"): entry for entry in lock.get("sources", {}).get("repos", [])}


def _print_repo_status(workspace: pathlib.Path, repo: dict, locked: dict | None) -> None:
    name = repo["name"]
    role = repo_role(repo)
    dst = workspace / "repos" / name
    role_tag = f"{name} ({role})"

    if not dst.exists():
        print(f"  {role_tag}: not fetched yet")
        return

    head_sha = try_run_git(["rev-parse", "HEAD"], cwd=dst)
    if head_sha is None:
        print(f"  {role_tag}: not a git repo at {dst}")
        return

    branch = try_run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=dst) or "?"
    is_dirty = working_tree_dirty(dst)
    locked_sha = (locked or {}).get("commit")

    if role == "edit":
        details = [f"branch: {branch}"]
        if locked_sha and head_sha == locked_sha:
            details.append("at lock SHA (unchanged)")
        elif locked_sha:
            details.append(f"HEAD={head_sha[:12]} lock={locked_sha[:12]}")
        if is_dirty:
            details.append("dirty")
        print(f"  {role_tag}: " + ", ".join(details))

        if not is_dirty:
            upstream_sha = try_run_git(
                ["rev-parse", "--verify", "--quiet", f"origin/{repo['ref']}"], cwd=dst
            ) or try_run_git(["rev-parse", "--verify", repo["ref"]], cwd=dst)
            if (
                upstream_sha
                and upstream_sha != head_sha
                and is_ancestor(dst, head_sha, upstream_sha)
            ):
                ahead = commits_between(dst, head_sha, upstream_sha)
                print(f"      upstream {repo['ref']} is {ahead} commit(s) ahead")
                print(f"      -> git -C {dst} rebase {upstream_sha}")
        return

    details = [f"pin: {repo['ref']}"]
    if locked_sha and head_sha != locked_sha:
        details.append(f"DRIFT: HEAD={head_sha[:12]} lock={locked_sha[:12]}")
    elif is_dirty:
        details.append("DIRTY working tree")
    else:
        details.append("clean")
    print(f"  {role_tag}: " + ", ".join(details))


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
    lock = read_json(lock_path) if lock_path.exists() else None
    locked_index = _locked_repo_index(lock) if lock else {}

    repos = sources.get("repos", [])
    edit_repos = [r for r in repos if repo_role(r) == "edit"]
    ref_repos = [r for r in repos if repo_role(r) == "reference"]

    if edit_repos:
        print("Edit repos:")
        for repo in edit_repos:
            _print_repo_status(workspace, repo, locked_index.get(repo["name"]))
    if ref_repos:
        print("Reference repos:")
        for repo in ref_repos:
            _print_repo_status(workspace, repo, locked_index.get(repo["name"]))

    if lock:
        print(f"Lock updated: {lock.get('updated_at', 'unknown')}")
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


def try_run_git(args: list[str], cwd: pathlib.Path | None = None) -> str | None:
    """Run git, returning stdout on success or None on failure (silent)."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def working_tree_dirty(dst: pathlib.Path) -> bool:
    return bool(run_git(["status", "--porcelain"], cwd=dst))


def resolve_upstream_sha(dst: pathlib.Path, ref: str) -> str:
    """Resolve the upstream version of ``ref`` after a ``git fetch``.

    Tries ``origin/<ref>`` first (handles branches), then ``<ref>`` (handles tags
    and explicit SHAs). Raises if neither resolves.
    """
    sha = try_run_git(["rev-parse", "--verify", "--quiet", f"origin/{ref}"], cwd=dst)
    if sha:
        return sha
    return run_git(["rev-parse", "--verify", ref], cwd=dst)


def is_ancestor(dst: pathlib.Path, ancestor_sha: str, descendant_sha: str) -> bool:
    """True if ``ancestor_sha`` is reachable from ``descendant_sha``."""
    if ancestor_sha == descendant_sha:
        return True
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha],
        cwd=dst,
        capture_output=True,
    )
    return result.returncode == 0


def commits_between(dst: pathlib.Path, ancestor_sha: str, descendant_sha: str) -> int:
    """Count commits in ``ancestor_sha..descendant_sha`` (0 if not ancestor)."""
    if ancestor_sha == descendant_sha:
        return 0
    output = try_run_git(
        ["rev-list", "--count", f"{ancestor_sha}..{descendant_sha}"],
        cwd=dst,
    )
    if output is None:
        return 0
    try:
        return int(output)
    except ValueError:
        return 0


def fetch_reference_repo(workspace: pathlib.Path, repo: dict) -> dict:
    name = repo["name"]
    dst = workspace / "repos" / name

    if dst.exists():
        if working_tree_dirty(dst):
            raise SystemExit(
                f"{name} (reference) has local changes; refusing to overwrite. "
                f"Discard them with `git -C {dst} checkout .` or change the role to 'edit'."
            )
        print(f"Fetching {name} (reference)...")
        run_git(["fetch", "--tags", "--prune"], cwd=dst)
        run_git(["checkout", repo["ref"]], cwd=dst)
    else:
        print(f"Cloning {name} (reference)...")
        run_git(["clone", repo["url"], str(dst)])
        run_git(["checkout", repo["ref"]], cwd=dst)

    commit = run_git(["rev-parse", "HEAD"], cwd=dst)
    print(f"Locked {name} @ {commit[:12]}")
    return {
        "name": name,
        "url": repo["url"],
        "ref": repo["ref"],
        "role": "reference",
        "commit": commit,
        "path": str(dst.relative_to(workspace)),
        "dirty": False,
        "fetched_at": utc_now(),
    }


def fetch_edit_repo(workspace: pathlib.Path, repo: dict, do_rebase: bool) -> dict:
    name = repo["name"]
    dst = workspace / "repos" / name

    if not dst.exists():
        print(f"Cloning {name} (edit)...")
        run_git(["clone", repo["url"], str(dst)])
        run_git(["checkout", repo["ref"]], cwd=dst)
        commit = run_git(["rev-parse", "HEAD"], cwd=dst)
        print(f"Locked {name} @ {commit[:12]} — create a branch before committing")
        return {
            "name": name,
            "url": repo["url"],
            "ref": repo["ref"],
            "role": "edit",
            "commit": commit,
            "path": str(dst.relative_to(workspace)),
            "dirty": False,
            "fetched_at": utc_now(),
        }

    print(f"Fetching {name} (edit)...")
    run_git(["fetch", "--tags", "--prune"], cwd=dst)
    upstream_sha = resolve_upstream_sha(dst, repo["ref"])
    head_sha = run_git(["rev-parse", "HEAD"], cwd=dst)
    is_dirty = working_tree_dirty(dst)
    behind = (
        head_sha != upstream_sha and is_ancestor(dst, head_sha, upstream_sha)
    )
    behind_count = commits_between(dst, head_sha, upstream_sha) if behind else 0

    if behind and not is_dirty and do_rebase:
        run_git(["rebase", upstream_sha], cwd=dst)
        head_sha = run_git(["rev-parse", "HEAD"], cwd=dst)
        is_dirty = working_tree_dirty(dst)
        print(f"  rebased onto {repo['ref']} @ {upstream_sha[:12]}")
    elif behind and not is_dirty:
        print(
            f"  HEAD={head_sha[:12]} is behind {repo['ref']}={upstream_sha[:12]} "
            f"by {behind_count} commit(s); working tree clean"
        )
        print(f"  to advance:  git -C {dst} rebase {upstream_sha}")
        print(f"  or run:      zentaizo fetch --rebase")
    else:
        dirty_label = "dirty" if is_dirty else "clean"
        print(
            f"  HEAD={head_sha[:12]} ({dirty_label}); upstream {repo['ref']}={upstream_sha[:12]}"
        )

    print(f"Locked {name} @ upstream {upstream_sha[:12]}")
    return {
        "name": name,
        "url": repo["url"],
        "ref": repo["ref"],
        "role": "edit",
        "commit": upstream_sha,
        "head": head_sha,
        "path": str(dst.relative_to(workspace)),
        "dirty": is_dirty,
        "fetched_at": utc_now(),
    }


def fetch_workspace(args: argparse.Namespace) -> int:
    workspace, config = load_workspace(args.workspace)
    sources = source_groups(config)
    repos = sources.get("repos", [])
    lock = (
        read_json(workspace / LOCK_NAME)
        if (workspace / LOCK_NAME).exists()
        else initial_lock(config.get("name", workspace.name))
    )
    do_rebase = bool(getattr(args, "rebase", False))
    locked_repos: list[dict] = []

    for repo in repos:
        if repo_role(repo) == "edit":
            locked_repos.append(fetch_edit_repo(workspace, repo, do_rebase))
        else:
            locked_repos.append(fetch_reference_repo(workspace, repo))

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
    create.add_argument(
        "--no-skills",
        action="store_true",
        help="skip copying bundled skills/ markdown into the workspace",
    )
    create.set_defaults(func=create_workspace)

    validate = sub.add_parser("validate", help="validate a workspace atlas")
    validate.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    validate.set_defaults(func=validate_workspace)

    status = sub.add_parser("status", help="show workspace source and lock status")
    status.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    status.set_defaults(func=status_workspace)

    fetch = sub.add_parser("fetch", help="fetch repo snapshots and update the lock file")
    fetch.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    fetch.add_argument(
        "--rebase",
        action="store_true",
        help="rebase clean edit repos that are behind their upstream ref",
    )
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
