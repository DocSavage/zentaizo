import argparse
import contextlib
import importlib.util
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "src/zentaizo/templates/global-skills/zentaizo/scripts/render_report_pdf.py"
)


def load_renderer():
    spec = importlib.util.spec_from_file_location("zentaizo_report_pdf_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load report renderer: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReportPdfRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = load_renderer()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def args_for(self, source: Path, **overrides):
        values = {
            "source": source,
            "theme": "auto",
            "title": None,
            "subtitle": None,
            "organization": None,
            "eyebrow": None,
            "cover_note": None,
            "status": None,
            "current_as_of": None,
            "fact": [],
            "cover_image": None,
            "page_break_before": [],
            "columns": [],
            "extra_css": None,
            "keep_html": None,
            "engine": "auto",
            "no_sandbox": False,
            "render_timeout": 120,
            "list_headings": False,
            "fail_on_unlinked_section_refs": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def build(self, markdown: str, name: str = "report.md", **overrides):
        source = self.tmp / name
        source.write_text(markdown, encoding="utf-8")
        return self.renderer.build_document(self.args_for(source, **overrides))

    def test_fenced_markdown_heading_does_not_split_body(self):
        document, _ = self.build(
            "# T\n\nIntro.\n\n```markdown\n## fake heading in code\n```\n\n"
            "## Real Section\n\nTAIL MARKER\n"
        )

        self.assertNotIn('<h2 id="fake-heading-in-code">', document)
        self.assertIn("## fake heading in code", document)
        self.assertIn('<h2 id="real-section">', document)
        self.assertIn('<p class="lead">TAIL MARKER</p>', document)

    def test_fenced_h1_is_not_used_as_title(self):
        document, _ = self.build(
            "Intro.\n\n```sh\n# fake title\n```\n\n## Real Section\n\nBody.\n",
            name="fallback-title.md",
        )

        self.assertIn("<h1>Fallback Title</h1>", document)
        self.assertNotIn("<h1>fake title</h1>", document)
        self.assertIn("# fake title", document)

    def test_mid_document_h1_is_removed_exactly_once(self):
        document, _ = self.build("Opening paragraph.\n\n# Real Title\n\n## Body\n\nText.\n")

        self.assertEqual(document.count("<h1>Real Title</h1>"), 1)
        self.assertIn("<p>Opening paragraph.</p>", document)

    def test_running_title_cannot_close_style_element(self):
        document, _ = self.build(
            "# Evil</style><img src=x onerror=alert(1)>: rest\n\n## Body\n\nText.\n"
        )

        self.assertNotIn("</style><img src=x onerror=alert(1)>", document)
        self.assertIn("\\3C /style>", document)
        self.assertIn(
            "<h1>Evil&lt;/style&gt;&lt;img src=x onerror=alert(1)&gt;: rest</h1>",
            document,
        )

    def test_theme_inference_matches_whole_keywords(self):
        self.assertEqual(
            self.renderer.infer_theme("Agentic change management", ""),
            "neutral",
        )
        self.assertEqual(
            self.renderer.infer_theme("Programming workshop room bookings", ""),
            "neutral",
        )
        self.assertEqual(
            self.renderer.infer_theme("Service hang postmortem", ""),
            "incident",
        )

    def test_deck_uses_first_body_paragraph_not_heading(self):
        document, _ = self.build("# Deck Test\n\n## Summary\n\nActual summary paragraph.\n")

        self.assertIn(
            '<div class="dek"><p>Actual summary paragraph.</p></div>',
            document,
        )
        self.assertNotIn('<div class="dek"><p>Summary</p></div>', document)

    def test_deck_is_omitted_without_a_paragraph(self):
        document, _ = self.build("# Deck Test\n\n## Summary\n\n```text\ncode\n```\n")

        self.assertIn('<div class="dek"></div>', document)

    def test_prelude_thematic_break_is_removed(self):
        document, _ = self.build("# HR Test\n\nIntro.\n\n---\n\nMore intro.\n\n## Body\n\nText.\n")

        introduction = document.split(
            '<section class="report-introduction">',
            1,
        )[1].split("</section>", 1)[0]
        self.assertNotIn("<hr", introduction)
        self.assertIn("<p>More intro.</p>", introduction)

    def test_strikethrough_and_task_lists_render(self):
        document, _ = self.build("# GFM\n\n## Body\n\n~~removed~~\n\n- [ ] open\n- [x] done\n")

        self.assertIn("<s>removed</s>", document)
        self.assertNotIn("~~removed~~", document)
        self.assertIn('class="task-list-item"', document)
        self.assertIn("☐ open", document)
        self.assertIn("☑ done", document)

    def test_branding_uses_frontmatter_and_neutral_defaults(self):
        branded, _ = self.build(
            "---\norganization: Example Org\ncover_note: Public release\n---\n"
            "# Branded\n\n## Body\n\nText.\n",
            name="branded.md",
        )
        neutral, _ = self.build("# Neutral\n\n## Body\n\nText.\n", name="neutral.md")

        self.assertIn("Example Org · Technical Report", branded)
        self.assertIn("Public release", branded)
        self.assertIn("Zentaizo · Technical Report", neutral)
        self.assertIn("Generated from the living Markdown report", neutral)
        self.assertNotIn("Janelia FlyEM", neutral)

    def test_remote_markdown_image_emits_warning(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            document, _ = self.build(
                "# Remote\n\n## Body\n\n![remote](https://example.invalid/pixel.png)\n"
            )

        self.assertIn("may fetch remote image URLs", stderr.getvalue())
        self.assertIn("https://example.invalid/pixel.png", document)

    def test_unlinked_section_reference_emits_actionable_warning(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.build(
                "# References\n\n## Confirm and respond\n\n"
                "See § *Confirm and respond*.\n"
            )

        warning = stderr.getvalue()
        self.assertIn("Unlinked section reference marker (§)", warning)
        self.assertIn("Markdown body line(s): 5", warning)
        self.assertIn("[§ *Section title*](#section-slug)", warning)

    def test_strict_cross_reference_check_rejects_unlinked_section_marker(self):
        with self.assertRaisesRegex(
            SystemExit,
            r"Unlinked section reference marker \(§\)",
        ):
            self.build(
                "# References\n\n## Confirm and respond\n\n"
                "See § *Confirm and respond*.\n",
                fail_on_unlinked_section_refs=True,
            )

    def test_linked_and_code_section_markers_do_not_warn(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            document, _ = self.build(
                "# References\n\n## Confirm and respond\n\n"
                "See [§ *Confirm and respond*](#confirm-and-respond).\n\n"
                "The literal `§` is not a cross-reference.\n\n"
                "```text\n§ is literal here too\n```\n",
                fail_on_unlinked_section_refs=True,
            )

        self.assertEqual(stderr.getvalue(), "")
        self.assertIn('href="#confirm-and-respond"', document)

    def test_hash_table_header_gets_compact_index_column(self):
        document, _ = self.build(
            "# Table\n\n## Steps\n\n"
            "| # | Action | Expect |\n"
            "|---|---|---|\n"
            "| 1 | Retry | Works |\n"
        )

        self.assertIn(
            'class="report-table table-steps-1 compact-index-column"',
            document,
        )

    def test_chrome_is_sandboxed_by_default_and_has_timeout(self):
        html_path = self.tmp / "report.html"
        html_path.write_text("<html></html>", encoding="utf-8")
        output = self.tmp / "report.pdf"
        commands = []

        def fake_run(command, **kwargs):
            commands.append((command, kwargs))
            output.write_bytes(b"%PDF")
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(self.renderer, "find_chrome", return_value="/chrome"),
            mock.patch.object(self.renderer.shutil, "which", return_value=None),
            mock.patch.object(self.renderer.subprocess, "run", side_effect=fake_run),
        ):
            selected = self.renderer.render_pdf(
                html_path,
                output,
                "chrome",
                timeout_seconds=7,
            )

        self.assertEqual(selected, "chrome")
        self.assertNotIn("--no-sandbox", commands[0][0])
        self.assertEqual(commands[0][1]["timeout"], 7)

    def test_chrome_no_sandbox_requires_explicit_option(self):
        html_path = self.tmp / "report.html"
        html_path.write_text("<html></html>", encoding="utf-8")
        output = self.tmp / "report.pdf"
        command_seen = []

        def fake_run(command, **kwargs):
            command_seen.extend(command)
            output.write_bytes(b"%PDF")
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(self.renderer, "find_chrome", return_value="/chrome"),
            mock.patch.object(self.renderer.shutil, "which", return_value=None),
            mock.patch.object(self.renderer.subprocess, "run", side_effect=fake_run),
        ):
            self.renderer.render_pdf(
                html_path,
                output,
                "chrome",
                no_sandbox=True,
            )

        self.assertIn("--no-sandbox", command_seen)

    def test_auto_engine_warns_when_falling_back_to_weasyprint(self):
        html_path = self.tmp / "report.html"
        html_path.write_text("<html></html>", encoding="utf-8")
        output = self.tmp / "report.pdf"

        def fake_run(command, **kwargs):
            output.write_bytes(b"%PDF")
            return subprocess.CompletedProcess(command, 0, "", "")

        stderr = io.StringIO()
        with (
            mock.patch.object(self.renderer, "find_chrome", return_value=None),
            mock.patch.object(
                self.renderer.shutil,
                "which",
                side_effect=lambda name: "/weasyprint"
                if name == "weasyprint"
                else None,
            ),
            mock.patch.object(self.renderer.subprocess, "run", side_effect=fake_run),
            contextlib.redirect_stderr(stderr),
        ):
            selected = self.renderer.render_pdf(html_path, output, "auto")

        self.assertEqual(selected, "weasyprint")
        self.assertIn("falling back to WeasyPrint", stderr.getvalue())

    def test_renderer_timeout_is_focused(self):
        html_path = self.tmp / "report.html"
        html_path.write_text("<html></html>", encoding="utf-8")
        output = self.tmp / "report.pdf"

        with (
            mock.patch.object(self.renderer, "find_chrome", return_value="/chrome"),
            mock.patch.object(self.renderer.shutil, "which", return_value=None),
            mock.patch.object(
                self.renderer.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["chrome"], 3),
            ),
            self.assertRaisesRegex(SystemExit, "3-second timeout"),
        ):
            self.renderer.render_pdf(
                html_path,
                output,
                "chrome",
                timeout_seconds=3,
            )


if __name__ == "__main__":
    unittest.main()
