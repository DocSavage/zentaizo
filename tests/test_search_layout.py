"""Behavior tests for the search layout (#15), run with the real rg and ugrep.

pixi.toml installs both tools, so `pixi run check` runs these tests. A test
skips when a tool it needs is missing, so plain `python -m unittest` passes.
ugrep runs with the flags that Claude Code's `grep` wrapper adds, so its
results match what an agent's root `grep -rl` sees.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from zentaizo.cli import main

RG = shutil.which("rg")
UGREP = shutil.which("ugrep")
MARKER = "zentaizo-search-marker-7f3c"
# The flags Claude Code's `grep` wrapper passes to its embedded ugrep.
CLAUDE_GREP_FLAGS = [
    "-G",
    "--ignore-files",
    "--hidden",
    "-I",
    "--exclude-dir=.git",
    "--exclude-dir=.svn",
    "--exclude-dir=.hg",
    "--exclude-dir=.bzr",
    "--exclude-dir=.jj",
    "--exclude-dir=.sl",
]
GEN6_GITIGNORE = "repos/\n.zentaizo/\ntmp/\ngraphify-out/\ndocs/snapshots/*.flagged.*\n"
NOTE = "sessions/questions/note.md"
# What a root search should find: the nested repo's own code, the
# git-worktree repo and the note. It should skip svc's vendor/ (search_exclude),
# its build/ and repos/inner/ (svc's own .gitignore), and the symlinked repo.
ROOT_HITS = ["repos/svc/src/auth.py", "repos/wt/wt.py", NOTE]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _seed_repo(root: Path, name: str, files: dict[str, str]) -> Path:
    """Create a bare repo whose `main` holds ``files``, and return its path."""
    bare = root / "origin" / f"{name}.git"
    bare.mkdir(parents=True)
    _git(bare, "init", "-q", "--bare", "-b", "main")
    work = root / "seed" / name
    work.mkdir(parents=True)
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "Test")
    for rel, text in files.items():
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "seed")
    _git(work, "push", "-q", str(bare), "main")
    return bare


def _quiet_main(argv: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main(argv)


class SearchLayoutBehaviorTests(unittest.TestCase):
    """A workspace that the dev build creates and fetches, searched from its root.

    The fixture rebuilds the 2026-11-03 scratch replica: a nested repo `svc`
    with vendored, build and nested-`repos/` markers; a symlinked repo
    `linked`; a git-worktree repo `wt`; and a note in `sessions/`.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        marker = f"{MARKER}\n"
        svc = _seed_repo(
            root,
            "svc",
            {
                ".gitignore": "build/\nrepos/\n",
                "src/auth.py": marker,
                "vendor/boost/config.hpp": marker,
            },
        )
        wt = _seed_repo(root, "wt", {"wt.py": marker})
        linked = _seed_repo(root, "linked", {"lib.py": marker})

        workspace = root / "ws"
        self.assertEqual(_quiet_main(["create", str(workspace), "--no-claude-hooks"]), 0)
        atlas = {
            "version": 1,
            "name": "search-layout",
            "sources": {
                "repos": [
                    {
                        "name": "svc",
                        "url": str(svc),
                        "ref": "main",
                        "role": "edit",
                        "search_exclude": ["vendor/"],
                    },
                    {"name": "wt", "url": str(wt), "ref": "main", "role": "edit"},
                    {"name": "linked", "url": str(linked), "ref": "main", "role": "reference"},
                ],
                "docs": [],
                "papers": [],
                "notes": [],
            },
        }
        (workspace / "zentaizo.atlas.json").write_text(json.dumps(atlas))

        # `wt` is a git worktree of a clone outside the workspace, and `linked`
        # is a symlink to another outside clone.
        outside = root / "outside"
        outside.mkdir()
        _git(outside, "clone", "-q", str(wt), "wt-main")
        _git(
            outside / "wt-main",
            "worktree",
            "add",
            "-q",
            "-b",
            "work",
            str(workspace / "repos" / "wt"),
        )
        _git(outside, "clone", "-q", str(linked), "linked")
        (workspace / "repos" / "linked").symlink_to(outside / "linked", target_is_directory=True)

        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["fetch", str(workspace)]), 0)
        self.fetch_output = out.getvalue()

        # Local files the repo's own .gitignore hides: build output and a
        # nested repos/ directory.
        for rel in ("build/out.txt", "repos/inner/inner.py"):
            path = workspace / "repos" / "svc" / rel
            path.parent.mkdir(parents=True)
            path.write_text(marker)
        (workspace / NOTE).write_text(marker)

        # Keep the searches hermetic: no global gitignore or rg config.
        home = root / "home"
        home.mkdir()
        self.env = {
            **{k: v for k, v in os.environ.items() if k != "RIPGREP_CONFIG_PATH"},
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
        }
        self.workspace = workspace

    def _search(self, tool: str | None, name: str, argv: list[str]) -> list[str]:
        if tool is None:
            self.skipTest(f"{name} is not installed; `pixi install` provides it")
        result = subprocess.run(
            [tool, *argv],
            cwd=self.workspace,
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        # Both tools exit 1 when nothing matches.
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return sorted(line.removeprefix("./") for line in result.stdout.splitlines())

    def _rg(self, *paths: str) -> list[str]:
        return self._search(RG, "rg", ["-l", MARKER, *paths])

    def _ugrep(self, *paths: str) -> list[str]:
        return self._search(UGREP, "ugrep", [*CLAUDE_GREP_FLAGS, "-rl", MARKER, *paths])

    def test_root_search_finds_repo_code_and_skips_what_it_should(self):
        self.assertEqual(self._rg(), ROOT_HITS)
        self.assertEqual(self._ugrep(), ROOT_HITS)

    def test_a_symlinked_repo_is_found_by_path(self):
        self.assertEqual(self._rg("repos/linked/"), ["repos/linked/lib.py"])
        self.assertEqual(self._ugrep("repos/linked/"), ["repos/linked/lib.py"])

    def test_generation_6_gitignore_hides_the_repos_from_both_tools(self):
        # The old failure: a generation-6 workspace finds only the note.
        (self.workspace / ".gitignore").write_text(GEN6_GITIGNORE)
        (self.workspace / ".ignore").unlink()
        self.assertEqual(self._rg(), [NOTE])
        self.assertEqual(self._ugrep(), [NOTE])

    def test_before_the_upgrade_the_ignore_block_helps_rg_but_not_ugrep(self):
        # A generation-6 workspace after a 0.19.0 fetch: `status` reports
        # "old layout" until the upgrade deletes the repos/ line.
        (self.workspace / ".gitignore").write_text(GEN6_GITIGNORE)
        self.assertEqual(self._rg(), ROOT_HITS)
        self.assertEqual(self._ugrep(), [NOTE])

    def test_each_tool_needs_the_vendored_path_in_its_own_file(self):
        # Why vendored paths go in both blocks: ugrep never reads .ignore, and
        # rg stops applying the outer .gitignore inside the nested repo.
        vendored = "repos/svc/vendor/boost/config.hpp"
        line = "/repos/svc/vendor/\n"
        for kept, missed_by in ((".ignore", self._ugrep), (".gitignore", self._rg)):
            dropped = ".gitignore" if kept == ".ignore" else ".ignore"
            path = self.workspace / dropped
            text = path.read_text()
            with self.subTest(only_in=kept):
                path.write_text(text.replace(line, ""))
                self.assertEqual(missed_by(), sorted([*ROOT_HITS, vendored]))
            path.write_text(text)

    def test_an_unanchored_negation_would_show_rg_a_nested_ignored_repos_dir(self):
        # Why the block anchors its patterns: `!repos/` re-includes every
        # directory named repos/, including svc's own ignored one.
        ignore = self.workspace / ".ignore"
        ignore.write_text(ignore.read_text().replace("!/repos/\n", "!repos/\n"))
        self.assertIn("repos/svc/repos/inner/inner.py", self._rg())

    def test_git_hides_repos_and_fetch_and_status_name_the_symlink(self):
        status = _git(self.workspace, "status", "--porcelain", "--untracked-files=all")
        self.assertEqual([line for line in status.splitlines() if "repos/" in line], [])
        self.assertIn("WARNING repos/linked is a symlink", self.fetch_output)
        self.assertNotIn("repos/wt is a symlink", self.fetch_output)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["status", str(self.workspace)]), 0)
        lines = out.getvalue().splitlines()
        index = lines.index(
            "Search: current — root grep and rg see repos/; 1 vendored path excluded"
        )
        self.assertTrue(lines[index + 1].startswith("  Symlinked repos: linked — "))


if __name__ == "__main__":
    unittest.main()
