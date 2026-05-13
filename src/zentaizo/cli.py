from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
from datetime import UTC, datetime
from importlib import resources

ATLAS_NAME = "zentaizo.atlas.json"
LEGACY_CONFIG_NAME = "zentaizo.config.json"
LOCK_NAME = "zentaizo.lock.json"
BEGIN_MARKER = "<!-- BEGIN zentaizo -->"
END_MARKER = "<!-- END zentaizo -->"
GLOBAL_SKILL_NAME = "zentaizo"
GLOBAL_SKILL_TARGETS = ("claude", "codex", "gemini")

VALID_ROLES = ("edit", "reference")
DEFAULT_ROLE = "reference"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_json(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise SystemExit(f"Missing file: {path}") from None
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

> Read [`AGENTS.md`](AGENTS.md) and follow the procedure in [`skills/curate-atlas.md`](skills/curate-atlas.md) to interview me and draft `{ATLAS_NAME}` for this project.

Do not assume your AI harness auto-discovers `AGENTS.md` or the `skills/` directory. Some do, some don't, and some discover them inconsistently. When in doubt, paste the exact paths into your prompt and ask the AI to read them first — the skill files carry the detailed procedure so prompts can stay short.

## Workflow

### 1. Curate the source atlas with AI assistance

Ask the AI to follow [`skills/curate-atlas.md`](skills/curate-atlas.md) and the instructions in [`AGENTS.md`](AGENTS.md) to interview you and draft `{ATLAS_NAME}`. If you've already had relevant design conversations with one or more AIs, drop the transcripts into `sessions/brainstorming/` first — the skill reads those before interviewing, so you don't repeat yourself.

```bash
$EDITOR {ATLAS_NAME}
```

### 2. Validate the atlas shape

```bash
zentaizo validate
```

### 3. Fetch source snapshots

```bash
zentaizo fetch
```

Repos marked `role: "edit"` are cloned once and then left alone on subsequent fetches so you can branch and commit freely. Repos marked `role: "reference"` are kept on their pinned ref; the AI is instructed (via [`AGENTS.md`](AGENTS.md)) not to modify them.

### 4. Prepare hierarchical summaries

```bash
zentaizo summarize
```

This writes a prompt under `summaries/`. Hand the prompt back to your AI to populate `summaries/overview.md`, `summaries/sources/`, and `summaries/relationships.md`.

### 5. Plan and implement changes

For each multi-repo change, ask the AI to follow [`skills/plan-and-implement.md`](skills/plan-and-implement.md). Example prompt:

> Follow [`skills/plan-and-implement.md`](skills/plan-and-implement.md) to draft and execute a plan for <describe change>.

The skill handles the full lifecycle: read the atlas to find editable repos, draft the plan in `sessions/changes/YYYY-MM-DD-<slug>.md` using [`skills/plan-template.md`](skills/plan-template.md) as scaffold, run with `status: planned` → `in-progress` → `done`, and append a `## Outcome` section on completion.

### 6. Capture Q&A and debugging as they happen

Substantive cross-repo answers go in `sessions/questions/YYYY-MM-DD-<slug>.md`; bug investigations go in `sessions/debugging/YYYY-MM-DD-<slug>.md`. Ask the AI to write these as you work — future sessions will read them instead of re-deriving the same context. The conventions are in [`AGENTS.md`](AGENTS.md).

### 7. (Optional) Share this context with another repo

```bash
zentaizo provide-info /path/to/repo-you-are-editing
```

Injects a bounded reference block into that repo's `AGENTS.md` so an AI working in that repo can find this workspace.

## Refreshing the boilerplate

The generic files in this workspace (`AGENTS.md`, `README.md`, `skills/curate-atlas.md`, `skills/plan-template.md`) are owned by Zentaizo. When the CLI ships an update, refresh them in place:

```bash
zentaizo update --dry-run   # preview
zentaizo update              # apply
```

Your atlas, lock file, summaries, repos, and `sessions/` contents are not touched. Review with `git diff` before committing in case you had hand-edited any of the generic files.
"""


def workspace_agents(name: str) -> str:
    return f"""# Assistant Context

This directory is a Zentaizo workspace for `{name}`.

## First Task

If `{ATLAS_NAME}` is missing, make creating it the first task. Interview the user to identify the source material that defines this system, then draft `{ATLAS_NAME}` as the human-authored context atlas.

Before interviewing from scratch, check `sessions/brainstorming/` — if the user has already dropped AI chat transcripts, source inventories, or design conversations there, read them first and use them to draft the atlas. The interview then fills gaps rather than starting cold.

Read `skills/curate-atlas.md` for the full interview procedure and follow it. (If your host tool also exposes a `zentaizo` or `curate-atlas` skill, that skill loads the same file.) If `skills/curate-atlas.md` is missing, follow this workflow directly:

1. Identify the system boundary: the product, service, research area, or ecosystem this workspace should explain.
2. List core repositories, including services, frontends, clients, SDKs, shared libraries, schemas, deployment, tests, and examples. For each repo decide `role: "edit"` (user will modify) or `role: "reference"` (read-only context).
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

Prefer claims grounded in `{LOCK_NAME}` and source paths.

## Editable vs Reference Repos

Every repo entry in `{ATLAS_NAME}` carries a `role` field:

- `role: "edit"` — code the user is modifying in this workspace. Branch, commit, and run tests against it.
- `role: "reference"` — code consulted for context only. Treat the working tree as read-only: do not edit files, do not run formatters or linters that would rewrite them, and do not commit. Reading the code, summarizing ideas from it, and citing specific paths is expected and encouraged.

Repos without an explicit `role` are treated as `reference`. If a task seems to require editing a `reference` repo, stop and ask the user — usually the correct move is to change its role to `edit` in `{ATLAS_NAME}`, not to edit it ad hoc.

When proposing a plan or summarizing changes, name the editable repo(s) explicitly so the user can confirm scope. Do not restate the full edit/reference list as boilerplate in every plan; read it from `{ATLAS_NAME}` at the start of each session.

## Recording Work in `sessions/`

`sessions/` is the durable trail of how this workspace has been used. Prefer writing to it over leaving substantive work only in chat history. Four subdirectories exist:

- `sessions/brainstorming/` — freeform input. Drop AI chat transcripts, sketches, source inventories, and exploratory design conversations here. No required schema, no required filename pattern. This is the *pre-atlas* dumping ground used to inform `{ATLAS_NAME}` during curation; later it also holds open-ended design discussions that aren't yet executable plans.
- `sessions/changes/` — implementation plans for multi-repo changes. Before editing in earnest, save a plan as `sessions/changes/YYYY-MM-DD-<slug>.md` covering problem, files involved, step-by-step approach, and verification. Use the status frontmatter convention below so a single file tracks the work from planning through delivery. The full procedure (drafting → executing → closing out) is in `skills/plan-and-implement.md`; `skills/plan-template.md` is the scaffold it copies.
- `sessions/questions/` — Q&A logs. When the user asks a substantive cross-repo question and you produce a researched answer, save the question, the answer, and source citations as `sessions/questions/YYYY-MM-DD-<slug>.md`.
- `sessions/debugging/` — traces, hypotheses, and resolutions. When investigating a bug across the atlas, save the trace and final root cause as `sessions/debugging/YYYY-MM-DD-<slug>.md`.

Filenames in `changes/`, `questions/`, and `debugging/` should sort chronologically. The slug should be 2–5 hyphenated words describing the topic (`shortener-link-expiration-contract`, not `plan1`).

### Status frontmatter for `sessions/changes/`

Each plan file begins with YAML frontmatter:

```yaml
---
status: planned          # planned | in-progress | done | abandoned
created: YYYY-MM-DD
updated: YYYY-MM-DD
editable_repos: [name, ...]   # repos this plan will modify; must have role: edit in the atlas
---
```

The body uses two top-level sections:

- `## Plan` — written before work starts: problem statement, scope, files involved, step-by-step approach, acceptance criteria, and verification. Treat this section as frozen once status moves to `in-progress`; edit it only to correct factual errors.
- `## Outcome` — appended when status moves to `done` (or `abandoned`): what was actually built, deviations from the plan and why, surprises, follow-up work, and links to commits or PRs.

Update `status:` and `updated:` whenever the state changes. Do not move or rename the file when work completes — the same path holds intent and result so future sessions can read both.

## From Brainstorming to Plan

When the user shares a design conversation, source inventory, or freeform implementation sketch:

1. Save the raw material under `sessions/brainstorming/` with a meaningful filename.
2. Separate workspace-generic facts from project-specific constraints. Generic facts (which repos exist, which are editable, what the system is) belong in `{ATLAS_NAME}`. Project-specific constraints (hardware targets, phase exclusions, acceptance criteria, reporting format) belong in the eventual `sessions/changes/` plan.
3. Run `skills/plan-and-implement.md` to distill the actionable parts into a `sessions/changes/YYYY-MM-DD-<slug>.md` plan. Link back to the brainstorming source(s) so the lineage is preserved.
"""


WORKSPACE_POINTER_MD = (
    "**For workspace instructions, see [`AGENTS.md`](AGENTS.md)** — it is the "
    "model-agnostic source of guidance for this Zentaizo workspace.\n"
)


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
        "sessions/brainstorming",
        "sessions/changes",
        "sessions/questions",
        "sessions/debugging",
    ]:
        (target / subdir).mkdir(parents=True, exist_ok=True)

    (target / "README.md").write_text(workspace_readme(name))
    (target / "AGENTS.md").write_text(workspace_agents(name))
    (target / "CLAUDE.md").write_text(WORKSPACE_POINTER_MD)
    (target / "GEMINI.md").write_text(WORKSPACE_POINTER_MD)
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


def update_workspace(args: argparse.Namespace) -> int:
    workspace = pathlib.Path(args.workspace).resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Not a directory: {workspace}")

    atlas = find_atlas(workspace)
    if atlas is not None:
        config = read_json(atlas)
        name = args.name or config.get("name") or workspace.name
    else:
        name = args.name or workspace.name

    dry_run = bool(getattr(args, "dry_run", False))
    skip_skills = bool(getattr(args, "no_skills", False))

    changes: list[tuple[str, str]] = []

    def apply_text(rel: str, target: pathlib.Path, new_text: str) -> None:
        if not target.exists():
            changes.append((rel, "create"))
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(new_text)
            return
        if target.read_text() != new_text:
            changes.append((rel, "update"))
            if not dry_run:
                target.write_text(new_text)
        else:
            changes.append((rel, "unchanged"))

    apply_text("AGENTS.md", workspace / "AGENTS.md", workspace_agents(name))
    apply_text("README.md", workspace / "README.md", workspace_readme(name))
    apply_text("CLAUDE.md", workspace / "CLAUDE.md", WORKSPACE_POINTER_MD)
    apply_text("GEMINI.md", workspace / "GEMINI.md", WORKSPACE_POINTER_MD)

    for subdir in ["brainstorming", "changes", "questions", "debugging"]:
        path = workspace / "sessions" / subdir
        if not path.exists():
            changes.append((f"sessions/{subdir}/", "create"))
            if not dry_run:
                path.mkdir(parents=True, exist_ok=True)

    if not skip_skills:
        skills_src = resources.files("zentaizo").joinpath("templates/skills")
        skills_dst = workspace / "skills"
        if not skills_dst.exists() and not dry_run:
            skills_dst.mkdir(parents=True, exist_ok=True)
        for entry in skills_src.iterdir():
            if not entry.is_file() or not entry.name.endswith(".md"):
                continue
            with resources.as_file(entry) as src_path:
                new_text = src_path.read_text()
            apply_text(f"skills/{entry.name}", skills_dst / entry.name, new_text)

    counts = {"create": 0, "update": 0, "unchanged": 0}
    for _, status in changes:
        counts[status] += 1

    label = "[dry-run] " if dry_run else ""
    print(
        f"{label}Update summary for {workspace}: "
        f"{counts['create']} created, {counts['update']} updated, {counts['unchanged']} unchanged"
    )
    for rel, status in changes:
        if status == "unchanged":
            continue
        prefix = "+ " if status == "create" else "~ "
        print(f"  {prefix}{rel}")

    if (counts["create"] or counts["update"]) and not dry_run:
        print("Review changes with `git diff`; restore any project-specific edits you had made.")
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
    behind = head_sha != upstream_sha and is_ancestor(dst, head_sha, upstream_sha)
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
        print("  or run:      zentaizo fetch --rebase")
    else:
        dirty_label = "dirty" if is_dirty else "clean"
        print(f"  HEAD={head_sha[:12]} ({dirty_label}); upstream {repo['ref']}={upstream_sha[:12]}")

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
        print(
            "Docs and papers are recorded in the lock file; snapshot download is a future command."
        )
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
            content = content[:begin] + block.rstrip() + content[end + len(END_MARKER) :]
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


def _global_skill_source() -> pathlib.Path:
    """Path to the canonical zentaizo meta-skill bundled in the package."""
    traversable = resources.files("zentaizo").joinpath(
        f"templates/global-skills/{GLOBAL_SKILL_NAME}"
    )
    return pathlib.Path(str(traversable))


def _claude_skills_root() -> pathlib.Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return pathlib.Path(base) / "skills"


def _codex_skills_root() -> pathlib.Path:
    base = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    return pathlib.Path(base) / "skills"


def _gemini_memory_file() -> pathlib.Path:
    base = os.environ.get("GEMINI_DIR") or os.path.expanduser("~/.gemini")
    return pathlib.Path(base) / "GEMINI.md"


def _expand_skill_targets(target: str) -> list[str]:
    if target == "all":
        return list(GLOBAL_SKILL_TARGETS)
    return [target]


def _install_folder_skill(source: pathlib.Path, dest_root: pathlib.Path, copy: bool) -> str:
    dest = dest_root / GLOBAL_SKILL_NAME
    dest_root.mkdir(parents=True, exist_ok=True)

    if dest.is_symlink():
        current_target = pathlib.Path(os.readlink(dest))
        if current_target == source:
            return f"already linked: {dest} -> {source}"
        return f"refusing to overwrite existing symlink {dest} -> {current_target}; uninstall first"
    if dest.exists():
        return f"refusing to overwrite existing {dest}; uninstall first"

    if not copy:
        try:
            dest.symlink_to(source, target_is_directory=True)
            return f"linked {dest} -> {source}"
        except OSError as exc:
            print(f"  symlink unavailable ({exc}); falling back to copy")

    shutil.copytree(source, dest)
    return f"copied {source} -> {dest}"


def _uninstall_folder_skill(dest_root: pathlib.Path) -> str:
    dest = dest_root / GLOBAL_SKILL_NAME
    if dest.is_symlink():
        dest.unlink()
        return f"removed symlink: {dest}"
    if dest.is_dir():
        shutil.rmtree(dest)
        return f"removed directory: {dest}"
    return f"nothing to remove at {dest}"


def _gemini_skill_block(source: pathlib.Path) -> str:
    skill_path = source / "SKILL.md"
    return "\n".join(
        [
            BEGIN_MARKER,
            "## Zentaizo Global Skill",
            "",
            "The `zentaizo` workflow builds curated multi-source AI context workspaces.",
            f"Read the full skill definition at `{skill_path}` when the user mentions zentaizo,",
            "context atlases, or multi-repo AI workspaces.",
            END_MARKER,
            "",
        ]
    )


def _install_gemini_block(source: pathlib.Path) -> str:
    path = _gemini_memory_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    block = _gemini_skill_block(source)

    if path.exists():
        existing = path.read_text()
        begin = existing.find(BEGIN_MARKER)
        end = existing.find(END_MARKER)
        if begin != -1 and end != -1:
            new_text = (
                existing[:begin].rstrip()
                + ("\n\n" if existing[:begin].strip() else "")
                + block.rstrip()
                + "\n\n"
                + existing[end + len(END_MARKER) :].lstrip()
            )
        else:
            new_text = existing.rstrip() + "\n\n" + block
    else:
        new_text = block

    path.write_text(new_text.rstrip() + "\n")
    return f"injected block into {path}"


def _uninstall_gemini_block() -> str:
    path = _gemini_memory_file()
    if not path.exists():
        return f"nothing to remove at {path}"
    text = path.read_text()
    begin = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if begin == -1 or end == -1:
        return f"no zentaizo block found in {path}"
    new_text = (text[:begin].rstrip() + "\n" + text[end + len(END_MARKER) :].lstrip()).strip()
    if new_text:
        path.write_text(new_text + "\n")
    else:
        path.unlink()
    return f"removed zentaizo block from {path}"


def _folder_skill_status(source: pathlib.Path, dest_root: pathlib.Path) -> str:
    dest = dest_root / GLOBAL_SKILL_NAME
    if dest.is_symlink():
        target = pathlib.Path(os.readlink(dest))
        if target == source:
            return f"{dest}: linked to package"
        return f"{dest}: symlink to {target}"
    if dest.is_dir():
        return f"{dest}: directory (copy)"
    if dest.exists():
        return f"{dest}: unexpected non-directory entry"
    return f"{dest}: not installed"


def _gemini_status() -> str:
    path = _gemini_memory_file()
    if not path.exists():
        return f"{path}: not installed (file missing)"
    if BEGIN_MARKER in path.read_text():
        return f"{path}: block injected"
    return f"{path}: file exists, no zentaizo block"


def skills_list(args: argparse.Namespace) -> int:
    source = _global_skill_source()
    print(f"Source: {source}")
    print(f"  claude  → {_folder_skill_status(source, _claude_skills_root())}")
    print(f"  codex   → {_folder_skill_status(source, _codex_skills_root())}")
    print(f"  gemini  → {_gemini_status()}")
    return 0


def skills_install(args: argparse.Namespace) -> int:
    source = _global_skill_source()
    if not source.exists():
        raise SystemExit(f"Cannot find packaged skill at {source}")
    for target in _expand_skill_targets(args.target):
        if target == "claude":
            print(f"claude:  {_install_folder_skill(source, _claude_skills_root(), args.copy)}")
        elif target == "codex":
            print(f"codex:   {_install_folder_skill(source, _codex_skills_root(), args.copy)}")
        elif target == "gemini":
            print(f"gemini:  {_install_gemini_block(source)}")
    return 0


def skills_uninstall(args: argparse.Namespace) -> int:
    for target in _expand_skill_targets(args.target):
        if target == "claude":
            print(f"claude:  {_uninstall_folder_skill(_claude_skills_root())}")
        elif target == "codex":
            print(f"codex:   {_uninstall_folder_skill(_codex_skills_root())}")
        elif target == "gemini":
            print(f"gemini:  {_uninstall_gemini_block()}")
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

    provide = sub.add_parser(
        "provide-info", help="inject Zentaizo context into another repo's AGENTS.md"
    )
    provide.add_argument("target", help="target repository directory")
    provide.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    provide.set_defaults(func=provide_info)

    update = sub.add_parser(
        "update",
        help="refresh generic Zentaizo files (AGENTS.md, README.md, skills, sessions/ subdirs) in an existing workspace",
    )
    update.add_argument("workspace", nargs="?", default=".", help="workspace directory")
    update.add_argument(
        "--name",
        help="override workspace name in templates (defaults to atlas name, then directory name)",
    )
    update.add_argument(
        "--dry-run",
        action="store_true",
        help="report changes without writing files",
    )
    update.add_argument(
        "--no-skills",
        action="store_true",
        help="skip updating skill files",
    )
    update.set_defaults(func=update_workspace)

    skills = sub.add_parser(
        "skills",
        help="register the global zentaizo meta-skill into Claude, Codex, or Gemini",
    )
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)

    skills_list_p = skills_sub.add_parser(
        "list", help="show install state of the global skill across AI tools"
    )
    skills_list_p.set_defaults(func=skills_list)

    target_choices = [*GLOBAL_SKILL_TARGETS, "all"]

    skills_install_p = skills_sub.add_parser(
        "install",
        help="register the meta-skill globally so AI tools see zentaizo from any directory",
    )
    skills_install_p.add_argument("--target", choices=target_choices, default="all")
    skills_install_p.add_argument(
        "--copy",
        action="store_true",
        help="copy files instead of symlinking (claude/codex only)",
    )
    skills_install_p.set_defaults(func=skills_install)

    skills_uninstall_p = skills_sub.add_parser(
        "uninstall", help="remove the global meta-skill registration"
    )
    skills_uninstall_p.add_argument("--target", choices=target_choices, default="all")
    skills_uninstall_p.set_defaults(func=skills_uninstall)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
