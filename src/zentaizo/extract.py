"""Optional-boundary wrapper for deterministic HTML main-content extraction."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module, metadata

EXTRACTION_PROFILE = "main-content-v1"


class ExtractionUnavailable(RuntimeError):
    """Trafilatura could not be imported or failed while extracting a page."""


@dataclass(frozen=True)
class ExtractResult:
    markdown: str
    version: str
    profile: str = EXTRACTION_PROFILE


def _load_trafilatura():
    return import_module("trafilatura")


def extract_main_content(html: str, url: str | None = None) -> ExtractResult | None:
    """Extract a page's main content as Markdown.

    ``None`` is a normal extractor decline (no usable main content). Import and
    runtime failures are normalized to ``ExtractionUnavailable`` so callers can
    fall back while making the failure loud.
    """
    try:
        trafilatura = _load_trafilatura()
    except Exception as exc:
        raise ExtractionUnavailable(f"trafilatura unavailable: {exc}") from exc

    try:
        markdown = trafilatura.extract(
            html,
            url=url,
            output_format="markdown",
            include_tables=True,
            include_comments=False,
            include_links=False,
        )
    except Exception as exc:
        raise ExtractionUnavailable(
            f"trafilatura extraction failed ({type(exc).__name__}: {exc})"
        ) from exc

    if not markdown or not markdown.strip():
        return None
    try:
        version = metadata.version("trafilatura")
    except metadata.PackageNotFoundError:
        version = getattr(trafilatura, "__version__", "unknown")
    return ExtractResult(markdown=markdown, version=version)
