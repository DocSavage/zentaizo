#!/usr/bin/env python3
"""Render a Markdown report as designed HTML and PDF."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

THEME_KEYWORDS = {
    "memory": (
        "memory",
        "fragmentation",
        "allocator",
        "page table",
        "ram",
        "oom",
        "compaction",
        "swap",
    ),
    "network": (
        "network",
        "request",
        "route",
        "proxy",
        "nginx",
        "http",
        "socket",
        "protocol",
    ),
    "incident": (
        "incident",
        "postmortem",
        "outage",
        "hang",
        "deadlock",
        "failure",
        "recovery",
        "root cause",
    ),
    "graph": (
        "graph",
        "connectome",
        "neuron",
        "topology",
        "dag",
        "segmentation",
        "labelmap",
        "merge",
    ),
    "data": (
        "dataset",
        "database",
        "storage",
        "warehouse",
        "neo4j",
        "pipeline",
        "analytics",
        "schema",
    ),
    "research": (
        "research",
        "experiment",
        "benchmark",
        "method",
        "paper",
        "analysis",
        "measurement",
        "hypothesis",
    ),
    "systems": (
        "system",
        "service",
        "container",
        "deployment",
        "infrastructure",
        "cluster",
        "swarm",
        "runtime",
    ),
}

THEME_LABELS = {
    "memory": "Memory Systems Report",
    "network": "Network Engineering Report",
    "incident": "Incident Postmortem",
    "graph": "Graph Systems Report",
    "data": "Data Platform Report",
    "research": "Technical Research Report",
    "systems": "Infrastructure Report",
    "neutral": "Technical Report",
}

PALETTES = {
    "memory": {
        "accent": "#0f8b8d",
        "accent_dark": "#08666b",
        "accent_light": "#9ce4de",
        "cover_start": "#102f47",
        "cover_mid": "#14515d",
        "cover_end": "#0f8b8d",
    },
    "network": {
        "accent": "#2380a8",
        "accent_dark": "#165a79",
        "accent_light": "#a7dcf0",
        "cover_start": "#112c46",
        "cover_mid": "#174c69",
        "cover_end": "#197aa0",
    },
    "incident": {
        "accent": "#d16a32",
        "accent_dark": "#94421f",
        "accent_light": "#f4c39f",
        "cover_start": "#2d2638",
        "cover_mid": "#653b45",
        "cover_end": "#b55831",
    },
    "graph": {
        "accent": "#5e7dc7",
        "accent_dark": "#405797",
        "accent_light": "#c4d0f3",
        "cover_start": "#202d4c",
        "cover_mid": "#364b75",
        "cover_end": "#5e68a8",
    },
    "data": {
        "accent": "#257f78",
        "accent_dark": "#185c58",
        "accent_light": "#a9ded6",
        "cover_start": "#15323f",
        "cover_mid": "#28565b",
        "cover_end": "#2f8278",
    },
    "research": {
        "accent": "#7355a5",
        "accent_dark": "#50387b",
        "accent_light": "#d3c4ed",
        "cover_start": "#242a46",
        "cover_mid": "#443c69",
        "cover_end": "#7355a5",
    },
    "systems": {
        "accent": "#16828e",
        "accent_dark": "#0d5d68",
        "accent_light": "#a7e0df",
        "cover_start": "#112f3e",
        "cover_mid": "#1c4d59",
        "cover_end": "#147a86",
    },
    "neutral": {
        "accent": "#087b83",
        "accent_dark": "#075c65",
        "accent_light": "#9fe1dc",
        "cover_start": "#102f47",
        "cover_mid": "#164b5a",
        "cover_end": "#087b83",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a Markdown report as a publication-style PDF."
    )
    parser.add_argument("source", type=Path, help="Markdown source path")
    parser.add_argument("-o", "--output", type=Path, help="PDF output path")
    parser.add_argument(
        "--theme",
        choices=("auto", *PALETTES),
        default="auto",
        help="cover-art theme (default: infer from report)",
    )
    parser.add_argument("--title", help="override report title")
    parser.add_argument("--subtitle", help="override cover deck")
    parser.add_argument(
        "--organization",
        help="cover organization (default: frontmatter organization or Zentaizo)",
    )
    parser.add_argument("--eyebrow", help="override cover eyebrow")
    parser.add_argument(
        "--cover-note",
        help="override the note at the bottom of the cover",
    )
    parser.add_argument("--status", help="override frontmatter status")
    parser.add_argument("--current-as-of", help="override frontmatter current_as_of")
    parser.add_argument(
        "--fact",
        action="append",
        default=[],
        metavar="VALUE|LABEL",
        help="cover fact card; repeat up to three times",
    )
    parser.add_argument("--cover-image", type=Path, help="optional cover image")
    parser.add_argument(
        "--page-break-before",
        action="append",
        default=[],
        metavar="SLUG",
        help="force a heading to start a page; repeat as needed",
    )
    parser.add_argument(
        "--columns",
        action="append",
        default=[],
        metavar="SLUG",
        help="render the first list after a heading in two columns",
    )
    parser.add_argument("--extra-css", type=Path, help="append report-specific CSS")
    parser.add_argument("--keep-html", type=Path, help="retain intermediate HTML")
    parser.add_argument(
        "--engine",
        choices=("auto", "chrome", "weasyprint"),
        default="auto",
    )
    parser.add_argument(
        "--no-sandbox",
        action="store_true",
        help="disable the Chrome sandbox when the environment requires it",
    )
    parser.add_argument(
        "--render-timeout",
        type=float,
        default=120,
        metavar="SECONDS",
        help="maximum renderer runtime (default: 120 seconds)",
    )
    parser.add_argument(
        "--list-headings",
        action="store_true",
        help="print heading slugs and exit without rendering",
    )
    parser.add_argument(
        "--fail-on-unlinked-section-refs",
        action="store_true",
        help="fail when a section marker (§) appears outside a Markdown link",
    )
    return parser.parse_args()


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    metadata: dict[str, str] = {}
    if not lines or lines[0].strip() != "---":
        return metadata, text

    end = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if end is None:
        return metadata, text

    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if match:
            metadata[match.group(1)] = match.group(2).strip().strip('"')

    return metadata, "\n".join(lines[end + 1 :]).lstrip()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-") or "section"


def keyword_count(text: str, keyword: str) -> int:
    return len(
        re.findall(
            rf"(?<!\w){re.escape(keyword)}(?!\w)",
            text,
        )
    )


def infer_theme(title: str, markdown: str) -> str:
    title_text = title.lower()
    body_text = markdown.lower()
    title_scores = {
        theme: sum(keyword_count(title_text, word) for word in words)
        for theme, words in THEME_KEYWORDS.items()
    }
    specific_title_scores = {
        theme: score for theme, score in title_scores.items() if theme != "systems" and score
    }
    title_winner, title_score = max(
        (specific_title_scores or title_scores).items(),
        key=lambda item: item[1],
    )
    if title_score:
        return title_winner

    scores = {
        theme: sum(keyword_count(body_text, word) for word in words)
        for theme, words in THEME_KEYWORDS.items()
    }
    winner, score = max(scores.items(), key=lambda item: item[1])
    return winner if score else "neutral"


def add_class(token: Any, class_name: str) -> None:
    current = token.attrGet("class") or ""
    token.attrSet("class", " ".join(part for part in (current, class_name) if part))


def parse_facts(values: list[str]) -> list[tuple[str, str]]:
    if len(values) > 3:
        raise SystemExit("At most three --fact values are supported.")
    facts: list[tuple[str, str]] = []
    for value in values:
        if "|" not in value:
            raise SystemExit(f"Invalid --fact {value!r}; use VALUE|LABEL.")
        headline, label = (part.strip() for part in value.split("|", 1))
        if not headline or not label:
            raise SystemExit(f"Invalid --fact {value!r}; both fields are required.")
        facts.append((headline, label))
    return facts


def compact_text(value: str, limit: int = 330) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rsplit(" ", 1)[0] + "…"


def inline_plain_text(token: Any) -> str:
    parts = []
    for child in token.children or []:
        if child.type in {"text", "code_inline"}:
            parts.append(child.content)
        elif child.type in {"softbreak", "hardbreak"}:
            parts.append(" ")
    return "".join(parts)


def first_table_header(tokens: list[Any], table_index: int) -> str:
    in_header = False
    for token in tokens[table_index + 1 :]:
        if token.type == "table_close":
            break
        if token.type == "th_open":
            in_header = True
        elif token.type == "th_close":
            in_header = False
        elif token.type == "inline" and in_header:
            return inline_plain_text(token)
    return ""


def first_paragraph_text(tokens: list[Any]) -> str:
    for index, token in enumerate(tokens):
        if token.type != "paragraph_open" or token.level != 0:
            continue
        for candidate in tokens[index + 1 :]:
            if candidate.type == "paragraph_close":
                break
            if candidate.type == "inline":
                return inline_plain_text(candidate)
    return ""


def format_task_list_items(tokens: list[Any]) -> None:
    list_items: list[Any] = []
    for token in tokens:
        if token.type == "list_item_open":
            list_items.append(token)
        elif token.type == "list_item_close":
            list_items.pop()
        elif token.type == "inline" and list_items:
            first_text = next(
                (child for child in token.children or [] if child.type == "text"),
                None,
            )
            if first_text is None:
                continue
            marker = re.match(r"^\[([ xX])\]\s+", first_text.content)
            if marker is None:
                continue
            symbol = "☑" if marker.group(1).lower() == "x" else "☐"
            first_text.content = f"{symbol} {first_text.content[marker.end() :]}"
            add_class(list_items[-1], "task-list-item")


def remote_image_sources(tokens: list[Any]) -> list[str]:
    sources = []
    for token in tokens:
        for child in token.children or []:
            if child.type != "image":
                continue
            source = child.attrGet("src") or ""
            if source.startswith(("http://", "https://")):
                sources.append(source)
    return sources


def unlinked_section_reference_lines(tokens: list[Any]) -> list[int]:
    lines = []
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        link_depth = 0
        for child in token.children:
            if child.type == "link_open":
                link_depth += 1
            elif child.type == "link_close":
                link_depth = max(0, link_depth - 1)
            elif child.type == "text" and link_depth == 0 and "§" in child.content:
                line = token.map[0] + 1 if token.map else 1
                lines.append(line)
    return sorted(set(lines))


def cover_svg(theme: str) -> str:
    if theme == "memory":
        holes = {(1, 4), (2, 2), (2, 6), (4, 1), (4, 5), (6, 3), (7, 6)}
        blocks = []
        for row in range(8):
            for column in range(8):
                if (row, column) in holes:
                    continue
                opacity = 0.16 + ((row * 3 + column * 5) % 5) * 0.055
                blocks.append(
                    f'<rect x="{52 + column * 58}" y="{58 + row * 58}" '
                    f'width="42" height="42" rx="5" opacity="{opacity:.3f}"/>'
                )
        body = "".join(blocks) + (
            '<rect x="168" y="500" width="274" height="50" rx="9" '
            'fill="none" stroke="currentColor" stroke-width="5" opacity=".8"/>'
            '<path d="M182 525h246" stroke="currentColor" stroke-width="4" '
            'stroke-dasharray="26 10" opacity=".75"/>'
        )
    elif theme == "network":
        body = """
          <g fill="none" stroke="currentColor" stroke-width="4" opacity=".62">
            <path d="M70 410L190 305L310 355L438 190L540 265"/>
            <path d="M105 150L190 305L330 120L438 190L500 445"/>
            <path d="M70 410L260 500L500 445"/>
          </g>
          <g fill="currentColor">
            <circle cx="70" cy="410" r="15"/><circle cx="105" cy="150" r="11"/>
            <circle cx="190" cy="305" r="19"/><circle cx="260" cy="500" r="13"/>
            <circle cx="310" cy="355" r="11"/><circle cx="330" cy="120" r="16"/>
            <circle cx="438" cy="190" r="20"/><circle cx="500" cy="445" r="18"/>
            <circle cx="540" cy="265" r="12"/>
          </g>
        """
    elif theme == "incident":
        body = """
          <g fill="none" stroke="currentColor">
            <path d="M45 335h82l28-118 48 248 42-170 34 40h58l28-96 44 191
                     40-105h126" stroke-width="8" stroke-linejoin="round"/>
            <path d="M55 500h500M55 135h500" stroke-width="2" opacity=".3"/>
          </g>
          <g fill="currentColor" opacity=".42">
            <rect x="78" y="470" width="20" height="54"/>
            <rect x="135" y="435" width="20" height="89"/>
            <rect x="192" y="495" width="20" height="29"/>
            <rect x="249" y="390" width="20" height="134"/>
            <rect x="306" y="450" width="20" height="74"/>
            <rect x="363" y="330" width="20" height="194"/>
            <rect x="420" y="410" width="20" height="114"/>
          </g>
        """
    elif theme == "graph":
        body = """
          <g fill="none" stroke="currentColor" stroke-width="3" opacity=".58">
            <path d="M92 180L215 95L330 170L460 92L530 220L420 330L520 470
                     L350 525L235 410L80 470L145 315Z"/>
            <path d="M215 95L235 410M330 170L145 315M460 92L420 330
                     M145 315L420 330M235 410L520 470"/>
          </g>
          <g fill="currentColor">
            <circle cx="92" cy="180" r="13"/><circle cx="215" cy="95" r="20"/>
            <circle cx="330" cy="170" r="15"/><circle cx="460" cy="92" r="12"/>
            <circle cx="530" cy="220" r="20"/><circle cx="420" cy="330" r="24"/>
            <circle cx="520" cy="470" r="12"/><circle cx="350" cy="525" r="17"/>
            <circle cx="235" cy="410" r="21"/><circle cx="80" cy="470" r="11"/>
            <circle cx="145" cy="315" r="16"/>
          </g>
        """
    elif theme == "data":
        body = """
          <g fill="none" stroke="currentColor" stroke-width="4">
            <ellipse cx="300" cy="130" rx="185" ry="58" opacity=".75"/>
            <path d="M115 130v95c0 32 83 58 185 58s185-26 185-58v-95" opacity=".7"/>
            <path d="M115 225v95c0 32 83 58 185 58s185-26 185-58v-95" opacity=".58"/>
            <path d="M115 320v95c0 32 83 58 185 58s185-26 185-58v-95" opacity=".46"/>
            <path d="M115 415v70c0 32 83 58 185 58s185-26 185-58v-70" opacity=".34"/>
          </g>
          <g fill="currentColor" opacity=".48">
            <circle cx="190" cy="118" r="8"/><circle cx="270" cy="145" r="10"/>
            <circle cx="355" cy="112" r="7"/><circle cx="410" cy="152" r="9"/>
          </g>
        """
    elif theme == "research":
        body = """
          <g fill="none" stroke="currentColor">
            <ellipse cx="305" cy="310" rx="240" ry="165" stroke-width="3" opacity=".3"/>
            <ellipse cx="305" cy="310" rx="188" ry="125" stroke-width="4" opacity=".42"/>
            <ellipse cx="305" cy="310" rx="128" ry="82" stroke-width="5" opacity=".58"/>
            <path d="M70 470C160 400 230 510 315 438S465 365 545 405"
                  stroke-width="5" opacity=".66"/>
          </g>
          <g fill="currentColor">
            <circle cx="145" cy="245" r="10"/><circle cx="225" cy="390" r="14"/>
            <circle cx="305" cy="310" r="18"/><circle cx="390" cy="220" r="12"/>
            <circle cx="470" cy="360" r="9"/>
          </g>
        """
    elif theme == "systems":
        body = """
          <g fill="none" stroke="currentColor" stroke-width="4">
            <rect x="70" y="95" width="155" height="105" rx="14"/>
            <rect x="375" y="95" width="155" height="105" rx="14"/>
            <rect x="222" y="262" width="155" height="105" rx="14"/>
            <rect x="70" y="430" width="155" height="105" rx="14"/>
            <rect x="375" y="430" width="155" height="105" rx="14"/>
            <path d="M225 147h150M148 200l104 62M452 200l-104 62
                     M252 367L148 430M348 367l104 63"/>
          </g>
          <g fill="currentColor" opacity=".55">
            <circle cx="300" cy="315" r="17"/>
            <circle cx="148" cy="147" r="10"/><circle cx="452" cy="147" r="10"/>
            <circle cx="148" cy="482" r="10"/><circle cx="452" cy="482" r="10"/>
          </g>
        """
    else:
        body = """
          <g fill="none" stroke="currentColor">
            <circle cx="370" cy="365" r="210" stroke-width="3" opacity=".3"/>
            <circle cx="370" cy="365" r="152" stroke-width="5" opacity=".45"/>
            <circle cx="370" cy="365" r="92" stroke-width="7" opacity=".62"/>
            <path d="M75 470C175 375 250 510 345 420S490 315 560 370"
                  stroke-width="5" opacity=".58"/>
          </g>
        """
    return (
        '<svg class="cover-art" viewBox="0 0 620 620" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f"{body}</svg>"
    )


def css_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("<", "\\3C ")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def build_document(args: argparse.Namespace) -> tuple[str, str]:
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise SystemExit(
            "render_report_pdf.py requires markdown-it-py. Install it only with user approval."
        ) from exc

    source = args.source.resolve()
    if not source.is_file():
        raise SystemExit(f"Markdown source not found: {source}")
    metadata, markdown = split_frontmatter(source.read_text(encoding="utf-8"))
    renderer = MarkdownIt(
        "commonmark",
        {"html": False, "linkify": False, "typographer": True},
    ).enable(["table", "strikethrough"])

    tokens = renderer.parse(markdown)
    unlinked_reference_lines = unlinked_section_reference_lines(tokens)
    if unlinked_reference_lines:
        locations = ", ".join(str(line) for line in unlinked_reference_lines)
        message = (
            "Unlinked section reference marker (§) outside a Markdown link in "
            f"paragraph(s) beginning at Markdown body line(s): {locations}. "
            "Use [§ *Section title*](#section-slug), or replace § when it is not "
            "a cross-reference."
        )
        if args.fail_on_unlinked_section_refs:
            raise SystemExit(message)
        print(f"Warning: {message}", file=sys.stderr)
    remote_images = remote_image_sources(tokens)
    if remote_images:
        print(
            "Warning: rendering this report may fetch remote image URLs: "
            + ", ".join(dict.fromkeys(remote_images)),
            file=sys.stderr,
        )
    title_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if token.type == "heading_open" and token.tag == "h1"
        ),
        None,
    )
    if title_index is not None:
        title_inline = tokens[title_index + 1]
        source_title = inline_plain_text(title_inline)
        title_end = next(
            index
            for index in range(title_index + 1, len(tokens))
            if tokens[index].type == "heading_close"
        )
        del tokens[title_index : title_end + 1]
    else:
        source_title = metadata.get("title")
    title = args.title or source_title or source.stem.replace("-", " ").title()
    theme = args.theme if args.theme != "auto" else infer_theme(title, markdown)

    first_section = next(
        (
            index
            for index, token in enumerate(tokens)
            if token.type == "heading_open" and token.tag == "h2"
        ),
        None,
    )
    if first_section is None:
        prelude_tokens: list[Any] = []
    else:
        prelude_tokens = [token for token in tokens[:first_section] if token.type != "hr"]
        tokens = tokens[first_section:]
    format_task_list_items(prelude_tokens)
    prelude_html = renderer.renderer.render(
        prelude_tokens,
        renderer.options,
        {},
    )
    prelude_summary = first_paragraph_text(prelude_tokens)

    format_task_list_items(tokens)
    used_slugs: dict[str, int] = {}
    headings: list[tuple[int, str, str]] = []
    current_heading = "document"
    table_counts: dict[str, int] = {}
    first_h2: str | None = None
    lead_pending = False
    column_pending = set(args.columns)

    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            level = int(token.tag[1:])
            heading_text = tokens[index + 1].content
            base_slug = slugify(heading_text)
            used_slugs[base_slug] = used_slugs.get(base_slug, 0) + 1
            suffix = used_slugs[base_slug]
            heading_id = base_slug if suffix == 1 else f"{base_slug}-{suffix}"
            token.attrSet("id", heading_id)
            if heading_id in args.page_break_before:
                add_class(token, "page-break-before")
            headings.append((level, heading_text, heading_id))
            current_heading = heading_id
            if level == 2 and first_h2 is None:
                first_h2 = heading_id
                lead_pending = True
        elif token.type == "paragraph_open" and token.level == 0 and lead_pending:
            add_class(token, "lead")
            lead_pending = False
        elif token.type in {"bullet_list_open", "ordered_list_open"}:
            if current_heading in column_pending:
                add_class(token, "two-columns")
                column_pending.remove(current_heading)
        elif token.type == "table_open":
            table_counts[current_heading] = table_counts.get(current_heading, 0) + 1
            add_class(
                token,
                f"report-table table-{current_heading}-{table_counts[current_heading]}",
            )
            if first_table_header(tokens, index) == "#":
                add_class(token, "compact-index-column")

    if args.list_headings:
        for level, label, heading_id in headings:
            print(f"h{level} {heading_id}\t{label}")
        raise SystemExit(0)

    body = renderer.renderer.render(tokens, renderer.options, {})
    if args.subtitle:
        deck = f"<p>{html.escape(args.subtitle)}</p>"
    elif prelude_summary:
        deck = f"<p>{html.escape(compact_text(prelude_summary))}</p>"
    else:
        first_paragraph = first_paragraph_text(tokens)
        deck = f"<p>{html.escape(compact_text(first_paragraph))}</p>" if first_paragraph else ""

    h2_items = [item for item in headings if item[0] == 2]
    toc_items = list(h2_items)
    if len(toc_items) < 7:
        included = {item[2] for item in toc_items}
        for item in headings:
            if item[0] == 3 and item[2] not in included:
                toc_items.append(item)
                included.add(item[2])
                if len(toc_items) == 12:
                    break
        order = {item[2]: index for index, item in enumerate(headings)}
        toc_items.sort(key=lambda item: order[item[2]])
    toc_items = toc_items[:12]
    toc_html = "\n".join(
        f'<a class="toc-item" href="#{html.escape(anchor)}">'
        f"<span>{number:02d}</span>{html.escape(label)}</a>"
        for number, (_, label, anchor) in enumerate(toc_items, start=1)
    )

    facts = parse_facts(args.fact)
    facts_html = ""
    if facts:
        cards = "\n".join(
            f'<div class="fact"><strong>{html.escape(value)}</strong>'
            f"<span>{html.escape(label)}</span></div>"
            for value, label in facts
        )
        facts_html = f'<div class="facts">{cards}</div>'

    if args.cover_image:
        image_path = args.cover_image.resolve()
        if not image_path.is_file():
            raise SystemExit(f"Cover image not found: {image_path}")
        art_html = (
            f'<img class="cover-image" src="{html.escape(image_path.as_uri())}" '
            'alt=""><div class="cover-image-overlay"></div>'
        )
    else:
        art_html = cover_svg(theme)

    status = args.status or metadata.get("status")
    current_as_of = args.current_as_of or metadata.get("current_as_of")
    organization = args.organization or metadata.get("organization") or "Zentaizo"
    cover_note = (
        args.cover_note or metadata.get("cover_note") or "Generated from the living Markdown report"
    )
    pills = []
    if status:
        pills.append(f'<div class="meta-pill">Status: {html.escape(status)}</div>')
    if current_as_of:
        pills.append(f'<div class="meta-pill">Current as of: {html.escape(current_as_of)}</div>')
    meta_html = f'<div class="meta-row">{"".join(pills)}</div>' if pills else ""

    palette = PALETTES[theme]
    palette_css = (
        ":root {\n"
        + "\n".join(
            [
                f"  --accent: {palette['accent']};",
                f"  --accent-dark: {palette['accent_dark']};",
                f"  --accent-light: {palette['accent_light']};",
                f"  --cover-start: {palette['cover_start']};",
                f"  --cover-mid: {palette['cover_mid']};",
                f"  --cover-end: {palette['cover_end']};",
            ]
        )
        + "\n}"
    )

    css_path = Path(__file__).resolve().parent.parent / "assets" / "report.css"
    css = css_path.read_text(encoding="utf-8")
    running_title = compact_text(title.split(":", 1)[0], 42)
    css = css.replace("%%RUNNING_TITLE%%", css_escape(running_title))
    extra_css = args.extra_css.read_text(encoding="utf-8") if args.extra_css else ""
    eyebrow = args.eyebrow or f"{organization} · {THEME_LABELS[theme]}"

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <base href="{html.escape(source.parent.as_uri())}/">
  <title>{html.escape(title)}</title>
  <style>
{css}
{palette_css}
{extra_css}
  </style>
</head>
<body>
  <section class="cover">
    {art_html}
    <div class="cover-content">
      <div class="eyebrow">{html.escape(eyebrow)}</div>
      <h1>{html.escape(title)}</h1>
      <div class="dek">{deck}</div>
      {meta_html}
      {facts_html}
      <nav class="toc">
        <div class="toc-title">Document map</div>
        <div class="toc-grid">{toc_html}</div>
      </nav>
    </div>
    <div class="cover-note">
      {html.escape(cover_note)}
    </div>
  </section>
  <main>
    <section class="report-introduction">{prelude_html}</section>
    {body}
  </main>
</body>
</html>
"""
    return document, theme


def find_chrome() -> str | None:
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        command = shutil.which(name)
        if command:
            return command
    return None


def render_pdf(
    html_path: Path,
    output: Path,
    engine: str,
    *,
    no_sandbox: bool = False,
    timeout_seconds: float = 120,
) -> str:
    chrome = find_chrome()
    weasyprint = shutil.which("weasyprint")
    selected = engine
    if selected == "auto":
        selected = "chrome" if chrome else "weasyprint"
        if selected == "weasyprint" and weasyprint:
            print(
                "Chrome/Chromium was not found; falling back to WeasyPrint. "
                "Re-run the full visual QA because engine output differs.",
                file=sys.stderr,
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    if selected == "chrome":
        if not chrome:
            raise SystemExit(
                "Chrome/Chromium was not found. Install it with user approval "
                "or use --engine weasyprint."
            )
        command = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output}",
            html_path.resolve().as_uri(),
        ]
        if no_sandbox:
            command.insert(2, "--no-sandbox")
    else:
        if not weasyprint:
            raise SystemExit(
                "WeasyPrint was not found. Install it with user approval or use --engine chrome."
            )
        command = [weasyprint, str(html_path), str(output)]

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"PDF renderer exceeded the {timeout_seconds:g}-second timeout.") from exc
    if completed.returncode:
        details = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(f"PDF renderer failed ({completed.returncode}): {details}")
    if not output.is_file() or output.stat().st_size == 0:
        raise SystemExit(f"PDF renderer produced no output: {output}")
    return selected


def main() -> int:
    args = parse_args()
    if args.render_timeout <= 0:
        raise SystemExit("--render-timeout must be greater than zero.")
    args.source = args.source.resolve()
    output = (args.output or args.source.with_suffix(".pdf")).resolve()
    document, theme = build_document(args)

    if args.keep_html:
        html_path = args.keep_html.resolve()
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(document, encoding="utf-8")
        selected = render_pdf(
            html_path,
            output,
            args.engine,
            no_sandbox=args.no_sandbox,
            timeout_seconds=args.render_timeout,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="zentaizo-report-pdf-") as tmp:
            html_path = Path(tmp) / f"{args.source.stem}.html"
            html_path.write_text(document, encoding="utf-8")
            selected = render_pdf(
                html_path,
                output,
                args.engine,
                no_sandbox=args.no_sandbox,
                timeout_seconds=args.render_timeout,
            )

    print(f"Rendered {output}")
    print(f"Theme: {theme}; engine: {selected}; bytes: {output.stat().st_size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
