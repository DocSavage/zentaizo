import unittest
from types import SimpleNamespace
from unittest import mock

from zentaizo.extract import (
    EXTRACTION_PROFILE,
    ExtractionUnavailable,
    extract_main_content,
)


class ExtractMainContentTests(unittest.TestCase):
    def test_profile_and_version_are_recorded(self):
        backend = SimpleNamespace(extract=mock.Mock(return_value="# API\n\nBody"))
        with (
            mock.patch("zentaizo.extract._load_trafilatura", return_value=backend),
            mock.patch("zentaizo.extract.metadata.version", return_value="2.1.0"),
        ):
            result = extract_main_content("<html>body</html>", "https://example.com/api")

        self.assertIsNotNone(result)
        self.assertEqual(result.markdown, "# API\n\nBody")
        self.assertEqual(result.version, "2.1.0")
        self.assertEqual(result.profile, EXTRACTION_PROFILE)
        backend.extract.assert_called_once_with(
            "<html>body</html>",
            url="https://example.com/api",
            output_format="markdown",
            include_tables=True,
            include_comments=False,
            include_links=False,
        )

    def test_decline_returns_none(self):
        backend = SimpleNamespace(extract=mock.Mock(return_value=None))
        with mock.patch("zentaizo.extract._load_trafilatura", return_value=backend):
            self.assertIsNone(extract_main_content("<html></html>"))

    def test_import_and_runtime_failures_are_normalized(self):
        with (
            mock.patch(
                "zentaizo.extract._load_trafilatura",
                side_effect=ModuleNotFoundError("no trafilatura"),
            ),
            self.assertRaisesRegex(ExtractionUnavailable, "unavailable"),
        ):
            extract_main_content("<html></html>")

        backend = SimpleNamespace(extract=mock.Mock(side_effect=ValueError("bad tree")))
        with (
            mock.patch("zentaizo.extract._load_trafilatura", return_value=backend),
            self.assertRaisesRegex(ExtractionUnavailable, "bad tree"),
        ):
            extract_main_content("<html></html>")


if __name__ == "__main__":
    unittest.main()
