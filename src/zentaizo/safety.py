"""Sanitize and screen untrusted fetched content before it enters a workspace.

This is the fetch-time safety pass from the API/reference-docs design
(docs/design/api-reference-docs-layer.md, section 2.9). It runs *closest to the
source* — on downloaded doc content, before anything is written into the
workspace — because fetched material is committed to git and re-read by future
AI sessions, making a poisoned page a durable indirect-prompt-injection vector.

Honest scope: prompt-injection detection is undecidable in general. This module
does not *block* injection. It (1) reduces content to visible plain text,
(2) strips invisible/smuggling characters, and (3) *flags* injection signatures
for human review. Flagging is the weakest layer; it backstops the architectural
controls (quarantine, evidence-not-orders, human-in-the-loop), it does not
replace them.

Stdlib-only by design (the always-on baseline). Heavier scanners belong behind
the optional `zentaizo[docs-scan]` extra.
"""

from __future__ import annotations

import importlib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser

DeepScanner = Callable[[str], list[str]]
_deep_scanner_state = "none"

# Invisible / smuggling characters stripped in step 2.
#
# - Unicode Tags block (U+E0000–U+E007F): the ASCII-smuggling channel — visually
#   invisible but model-readable, used to hide instructions inside plain text.
# - Zero-width and word-joiner characters.
# - Bidi / directional overrides that can reorder displayed text.
# - The BOM / zero-width no-break space.
# Defined by code point (not literal glyphs) so the source stays readable and
# no invisible character can be mangled by an editor or pre-commit hook.
_ZERO_WIDTH = {
    chr(0x200B),  # zero-width space
    chr(0x200C),  # zero-width non-joiner
    chr(0x200D),  # zero-width joiner
    chr(0x2060),  # word joiner
    chr(0xFEFF),  # BOM / zero-width no-break space
}
_BIDI_CONTROLS = {
    chr(0x200E),  # left-to-right mark
    chr(0x200F),  # right-to-left mark
    chr(0x202A),  # left-to-right embedding
    chr(0x202B),  # right-to-left embedding
    chr(0x202C),  # pop directional formatting
    chr(0x202D),  # left-to-right override
    chr(0x202E),  # right-to-left override
    chr(0x2066),  # left-to-right isolate
    chr(0x2067),  # right-to-left isolate
    chr(0x2068),  # first strong isolate
    chr(0x2069),  # pop directional isolate
}


def _is_tag_char(ch: str) -> bool:
    return "\U000e0000" <= ch <= "\U000e007f"


def _is_other_invisible_control(ch: str) -> bool:
    # Strip C0/C1 control characters except common whitespace we want to keep.
    if ch in ("\t", "\n", "\r"):
        return False
    cat = unicodedata.category(ch)
    # Cc = control, Cf = format (e.g. soft hyphen, other invisibles).
    return cat in ("Cc", "Cf")


# Injection signatures scanned in step 3. Case-insensitive. These are *flagged*,
# never silently removed — docs legitimately discuss these strings, so a match
# means "a human should look", not "this is malicious".
_SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fake-role-tag", re.compile(r"</?\s*(system|assistant|user|developer)\b", re.I)),
    ("system-reminder-tag", re.compile(r"<\s*system[-_ ]?reminder", re.I)),
    ("chat-template-marker", re.compile(r"<\|\s*(im_start|im_end|endoftext)\s*\|>", re.I)),
    ("llama-inst-marker", re.compile(r"\[/?INST\]|<<\s*SYS\s*>>", re.I)),
    (
        "ignore-instructions",
        re.compile(r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+", re.I),
    ),
    (
        "disregard-instructions",
        re.compile(r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above)\b", re.I),
    ),
    (
        "override-persona",
        re.compile(r"\b(you\s+are\s+now|from\s+now\s+on,?\s+you|act\s+as)\b", re.I),
    ),
    (
        "conceal-from-user",
        re.compile(r"\bdo\s+not\s+(tell|inform|mention\s+to|reveal\s+to)\s+(the\s+)?user", re.I),
    ),
    ("tool-call-shape", re.compile(r"<\s*(antml:invoke|function_calls|tool_call|invoke)\b", re.I)),
)


@dataclass
class SafetyResult:
    """Outcome of sanitizing one piece of fetched content."""

    cleaned_text: str
    stripped: dict[str, int] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        """`flagged` if any injection signature matched, else `ok`."""
        return "flagged" if self.flags else "ok"

    def summary(self) -> str:
        stripped_total = sum(self.stripped.values())
        parts = [f"verdict={self.verdict}"]
        if stripped_total:
            detail = ", ".join(f"{k}={v}" for k, v in self.stripped.items() if v)
            parts.append(f"stripped {stripped_total} chars ({detail})")
        if self.flags:
            parts.append(f"{len(self.flags)} flag(s): " + "; ".join(self.flags))
        return " | ".join(parts)


class _TextExtractor(HTMLParser):
    """Collect visible text, dropping scripts, styles, and comments."""

    _SKIP_TAGS = {"script", "style", "head", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    # Comments are intentionally ignored (hidden content / injection surface).

    def text(self) -> str:
        return "".join(self._chunks)


def reduce_html_to_text(html: str) -> str:
    """Step 1: reduce HTML to visible text, dropping scripts/styles/comments."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return _normalize_whitespace(parser.text())


def _normalize_whitespace(text: str) -> str:
    # Conservative: trim trailing space per line, collapse 3+ blank lines to 2.
    lines = [line.rstrip() for line in text.splitlines()]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip("\n")


def strip_unsafe_unicode(text: str) -> tuple[str, dict[str, int]]:
    """Step 2: drop invisible/smuggling characters and NFC-normalize.

    Returns the cleaned text and a per-category count of removed characters.
    """
    counts = {"tag_chars": 0, "zero_width": 0, "bidi_controls": 0, "other_invisible": 0}
    kept: list[str] = []
    for ch in text:
        if _is_tag_char(ch):
            counts["tag_chars"] += 1
        elif ch in _ZERO_WIDTH:
            counts["zero_width"] += 1
        elif ch in _BIDI_CONTROLS:
            counts["bidi_controls"] += 1
        elif _is_other_invisible_control(ch):
            counts["other_invisible"] += 1
        else:
            kept.append(ch)
    cleaned = unicodedata.normalize("NFC", "".join(kept))
    return cleaned, counts


def scan_for_injection(text: str) -> list[str]:
    """Step 3: flag known injection signatures. Does not modify the text."""
    flags: list[str] = []
    for name, pattern in _SIGNATURES:
        match = pattern.search(text)
        if match:
            snippet = match.group(0).strip()
            flags.append(f"{name}: matched {snippet!r}")
    return flags


def load_deep_scanner() -> DeepScanner | None:
    """Return an llm-guard-backed scanner if [docs-scan] is installed and loads.

    Missing optional dependencies are an expected baseline path. Installed-but-broken
    scanners are warned about and treated as unavailable so fetch-docs never crashes.
    """
    global _deep_scanner_state
    try:
        adapter = importlib.import_module("zentaizo._llm_guard_scan")
    except ImportError:
        _deep_scanner_state = "none"
        return None

    try:
        if not adapter.ensure_available():
            _deep_scanner_state = "none" if adapter.state() == "missing" else "unavailable"
            return None
    except Exception as exc:
        print(f"WARNING: docs-scan backend failed to load ({exc}); using baseline only")
        _deep_scanner_state = "unavailable"
        return None

    _deep_scanner_state = "llm-guard"
    return adapter.scan


def deep_scanner_state() -> str:
    """State from the last load_deep_scanner() call."""
    return _deep_scanner_state


def sanitize(
    content: str, *, is_html: bool = False, deep_scan: DeepScanner | None = None
) -> SafetyResult:
    """Run the full fetch-time safety pass on one piece of content.

    `is_html=True` first reduces markup to visible text (step 1). Then strips
    invisible/smuggling characters (step 2) and flags injection signatures
    (step 3) on the result. When provided, `deep_scan` runs after the baseline
    pass and contributes extra findings to the same flags list.
    """
    text = reduce_html_to_text(content) if is_html else content
    cleaned, stripped = strip_unsafe_unicode(text)
    if not is_html:
        cleaned = _normalize_whitespace(cleaned)
    flags = scan_for_injection(cleaned)
    if deep_scan is not None:
        flags.extend(deep_scan(cleaned))
    return SafetyResult(cleaned_text=cleaned, stripped=stripped, flags=flags)
