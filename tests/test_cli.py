import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from zentaizo.cli import default_atlas, main


def write_example_atlas(workspace: Path, name: str = "example-atlas") -> None:
    (workspace / "zentaizo.atlas.json").write_text(json.dumps(default_atlas(name)))


class CliTests(unittest.TestCase):
    def test_create_starts_with_missing_atlas_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "example-atlas"
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["create", str(workspace)]), 0)
                self.assertEqual(main(["validate", str(workspace)]), 1)
                self.assertEqual(main(["status", str(workspace)]), 0)

            self.assertFalse((workspace / "zentaizo.atlas.json").exists())
            self.assertFalse((workspace / "zentaizo.lock.json").exists())
            self.assertTrue((workspace / "AGENTS.md").exists())

            agents = (workspace / "AGENTS.md").read_text()
            self.assertIn("If `zentaizo.atlas.json` is missing", agents)
            self.assertIn("Do not write to Claude Memory", agents)
            self.assertIn("skills/curate-atlas.md", agents)
            self.assertIn("sessions/brainstorming/", agents)
            self.assertIn("sessions/changes/", agents)
            self.assertIn("sessions/questions/", agents)
            self.assertIn("sessions/debugging/", agents)
            self.assertIn("Editable vs Reference Repos", agents)
            self.assertIn("status: planned", agents)
            self.assertIn("skills/plan-template.md", agents)
            self.assertIn("skills/plan-and-implement.md", agents)

            for subdir in ["brainstorming", "changes", "questions", "debugging"]:
                self.assertTrue((workspace / "sessions" / subdir).is_dir())

            readme = (workspace / "README.md").read_text()
            self.assertIn("[`skills/curate-atlas.md`](skills/curate-atlas.md)", readme)
            self.assertIn("[`skills/plan-template.md`](skills/plan-template.md)", readme)
            self.assertIn(
                "[`skills/plan-and-implement.md`](skills/plan-and-implement.md)",
                readme,
            )
            self.assertIn("sessions/brainstorming/", readme)
            self.assertIn("sessions/changes/", readme)
            self.assertIn("Plan and implement changes", readme)
            self.assertIn("auto-discovers", readme)
            self.assertNotIn("Do not write to assistant memory", readme)

            text = output.getvalue()
            self.assertIn("Created Zentaizo workspace", text)
            self.assertIn("Missing source atlas", text)
            self.assertIn("Atlas: missing zentaizo.atlas.json", text)

    def test_create_installs_curate_atlas_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "skill-atlas"

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create", str(workspace)]), 0)

            skill = workspace / "skills" / "curate-atlas.md"
            self.assertTrue(skill.exists())
            body = skill.read_text()
            self.assertIn("Curate the Zentaizo Atlas", body)
            self.assertNotIn("---\nname:", body[:200])

            plan = workspace / "skills" / "plan-template.md"
            self.assertTrue(plan.exists())
            plan_body = plan.read_text()
            self.assertIn("status: planned", plan_body)
            self.assertIn("## Plan", plan_body)
            self.assertIn("## Outcome", plan_body)

            procedure = workspace / "skills" / "plan-and-implement.md"
            self.assertTrue(procedure.exists())
            procedure_body = procedure.read_text()
            self.assertIn("Plan and Implement a Change", procedure_body)
            self.assertIn("status: planned", procedure_body)
            self.assertIn("role: \"edit\"", procedure_body)

    def test_create_no_skills_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "bare-atlas"

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create", str(workspace), "--no-skills"]), 0)

            self.assertFalse((workspace / "skills" / "curate-atlas.md").exists())

    def test_update_refreshes_stale_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "stale-atlas"

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create", str(workspace)]), 0)

            write_example_atlas(workspace, name="stale-atlas")

            agents_path = workspace / "AGENTS.md"
            agents_path.write_text("# stale content\n")
            (workspace / "skills" / "plan-template.md").unlink()

            brainstorming = workspace / "sessions" / "brainstorming"
            user_file = brainstorming / "design-chat.md"
            user_file.write_text("user content")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["update", str(workspace)]), 0)

            refreshed = agents_path.read_text()
            self.assertIn("Editable vs Reference Repos", refreshed)
            self.assertTrue((workspace / "skills" / "plan-template.md").exists())
            self.assertTrue(user_file.exists())
            self.assertEqual(user_file.read_text(), "user content")
            self.assertEqual(
                json.loads((workspace / "zentaizo.atlas.json").read_text())["name"],
                "stale-atlas",
            )

            text = output.getvalue()
            self.assertIn("~ AGENTS.md", text)
            self.assertIn("+ skills/plan-template.md", text)

    def test_update_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "dry-atlas"

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create", str(workspace)]), 0)

            agents_path = workspace / "AGENTS.md"
            agents_path.write_text("# stale content\n")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["update", str(workspace), "--dry-run"]), 0)

            self.assertEqual(agents_path.read_text(), "# stale content\n")
            self.assertIn("[dry-run]", output.getvalue())
            self.assertIn("~ AGENTS.md", output.getvalue())

    def test_update_creates_missing_sessions_subdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "legacy-atlas"

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create", str(workspace)]), 0)

            import shutil as _shutil
            _shutil.rmtree(workspace / "sessions" / "brainstorming")

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["update", str(workspace)]), 0)

            self.assertTrue((workspace / "sessions" / "brainstorming").is_dir())

    def test_validate_status_and_summarize_with_atlas(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "example-atlas"
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["create", str(workspace)]), 0)

            write_example_atlas(workspace)

            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["validate", str(workspace)]), 0)
                self.assertEqual(main(["status", str(workspace)]), 0)
                self.assertEqual(main(["summarize", str(workspace)]), 0)

            self.assertTrue((workspace / "zentaizo.atlas.json").exists())
            self.assertTrue((workspace / "AGENTS.md").exists())

            prompt = workspace / "summaries" / "summarize.prompt.md"
            self.assertTrue(prompt.exists())
            self.assertIn("Zentaizo Summary Task", prompt.read_text())

            text = output.getvalue()
            self.assertIn("Atlas: zentaizo.atlas.json", text)
            self.assertIn("valid", text)

    def test_validate_reports_missing_repo_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "bad-atlas"
            workspace.mkdir()
            (workspace / "zentaizo.atlas.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "bad",
                        "sources": {
                            "repos": [{"name": "api"}],
                            "docs": [],
                            "papers": [],
                            "notes": [],
                        },
                    }
                )
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["validate", str(workspace)]), 1)

            text = output.getvalue()
            self.assertIn("missing url", text)
            self.assertIn("missing ref", text)

    def test_validate_accepts_role_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "role-atlas"
            workspace.mkdir()
            (workspace / "zentaizo.atlas.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "role-atlas",
                        "sources": {
                            "repos": [
                                {
                                    "name": "core",
                                    "url": "https://example.com/core.git",
                                    "ref": "main",
                                    "role": "edit",
                                },
                                {
                                    "name": "ref-only",
                                    "url": "https://example.com/ref.git",
                                    "ref": "main",
                                    "role": "reference",
                                },
                                {
                                    "name": "implicit",
                                    "url": "https://example.com/impl.git",
                                    "ref": "main",
                                },
                            ],
                            "docs": [],
                            "papers": [],
                            "notes": [],
                        },
                    }
                )
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["validate", str(workspace)]), 0)

            text = output.getvalue()
            self.assertIn("valid", text)
            self.assertIn("3 repos (1 edit, 2 reference)", text)

    def test_validate_rejects_unknown_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "bad-role-atlas"
            workspace.mkdir()
            (workspace / "zentaizo.atlas.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "bad-role",
                        "sources": {
                            "repos": [
                                {
                                    "name": "core",
                                    "url": "https://example.com/core.git",
                                    "ref": "main",
                                    "role": "writable",
                                }
                            ],
                            "docs": [],
                            "papers": [],
                            "notes": [],
                        },
                    }
                )
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["validate", str(workspace)]), 1)

            text = output.getvalue()
            self.assertIn("invalid role", text)
            self.assertIn("'writable'", text)
            self.assertIn("'edit'", text)
            self.assertIn("'reference'", text)

    def test_legacy_config_file_still_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "legacy-atlas"
            workspace.mkdir()
            (workspace / "zentaizo.config.json").write_text(json.dumps(default_atlas("legacy-atlas")))

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["validate", str(workspace)]), 0)

            text = output.getvalue()
            self.assertIn("valid", text)
            self.assertIn("Atlas: zentaizo.config.json", text)

    def test_provide_info_injects_agents_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "context-atlas"
            target = Path(tmp) / "target-repo"
            target.mkdir()

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create", str(workspace)]), 0)
                write_example_atlas(workspace, name="context-atlas")
                self.assertEqual(main(["provide-info", str(target), str(workspace)]), 0)

            content = (target / "AGENTS.md").read_text()
            self.assertIn("BEGIN zentaizo", content)
            self.assertIn("Zentaizo Context", content)
            self.assertIn(str(workspace), content)


if __name__ == "__main__":
    unittest.main()
