import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from zentaizo.cli import main


class CliTests(unittest.TestCase):
    def test_create_validate_status_and_summarize(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "example-atlas"
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["create", str(workspace)]), 0)
                self.assertEqual(main(["validate", str(workspace)]), 0)
                self.assertEqual(main(["status", str(workspace)]), 0)
                self.assertEqual(main(["summarize", str(workspace)]), 0)

            self.assertTrue((workspace / "zentaizo.config.json").exists())
            self.assertTrue((workspace / "zentaizo.lock.json").exists())
            self.assertTrue((workspace / "AGENTS.md").exists())

            prompt = workspace / "summaries" / "summarize.prompt.md"
            self.assertTrue(prompt.exists())
            self.assertIn("Zentaizo Summary Task", prompt.read_text())

            text = output.getvalue()
            self.assertIn("Created Zentaizo workspace", text)
            self.assertIn("valid", text)

    def test_validate_reports_missing_repo_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "bad-atlas"
            workspace.mkdir()
            (workspace / "zentaizo.config.json").write_text(
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

    def test_provide_info_injects_agents_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "context-atlas"
            target = Path(tmp) / "target-repo"
            target.mkdir()

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["create", str(workspace)]), 0)
                self.assertEqual(main(["provide-info", str(target), str(workspace)]), 0)

            content = (target / "AGENTS.md").read_text()
            self.assertIn("BEGIN zentaizo", content)
            self.assertIn("Zentaizo Context", content)
            self.assertIn(str(workspace), content)


if __name__ == "__main__":
    unittest.main()
