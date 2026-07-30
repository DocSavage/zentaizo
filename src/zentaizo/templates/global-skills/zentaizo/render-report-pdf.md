# Render a polished report PDF

Follow this procedure only after the user asks for a PDF from a Markdown
report. Keep the Markdown source authoritative and unchanged unless the user
separately asks to edit it.

## 1. Choose the publishing path

Use the bundled `scripts/render_report_pdf.py` for a polished internal report
with a designed cover, fact cards, document map, tables, code blocks, running
footer, and topic-aware cover art.

Read `report-pdf-engines.md` before choosing another engine. Prefer Quarto for
executable research and citation-heavy multi-format publishing, Typst for a
maintained precision-typesetting system, and WeasyPrint for a production
HTML/CSS paged-media service. Pandoc is a strong converter but does not supply
publication design by itself.

Do not install missing software without user approval. The bundled renderer
requires a Python interpreter that can import `markdown_it`. Verify the exact
interpreter used below with `python3 -c "import markdown_it"`; installing
`zentaizo[report-pdf]` into an isolated pipx/uv tool environment does not make
the dependency available to an unrelated ambient interpreter. Chrome or
Chromium is the preferred PDF engine. In `--engine auto`, the renderer emits a
warning and falls back to WeasyPrint when Chrome is absent and WeasyPrint is
available; repeat the full visual QA after any fallback.

## 2. Inspect the report

1. Read the frontmatter, title, opening paragraphs, headings, tables, code
   blocks, images, links, and total length.
2. Identify three defensible facts for the cover. Prefer measured values,
   dates, counts, or outcomes central to the report. Do not invent or round
   unsupported numbers. Omit fact cards when the report has no honest set.
3. Select a cover theme:
   - `memory` — pages, allocation, kernels, OOM, fragmentation.
   - `network` — requests, routes, proxies, protocols, distributed traffic.
   - `incident` — outages, hangs, failures, recovery, postmortems.
   - `graph` — neurons, connectivity, labels, DAGs, topology.
   - `data` — databases, datasets, storage, ETL, analytics.
   - `research` — experiments, benchmarks, methods, papers.
   - `systems` — services, containers, deployment, infrastructure.
   - `neutral` — anything that does not fit.

   `--theme auto` scores the title and body. Override it when domain judgment
   is better than keywords.
4. Use the built-in vector motif by default. It is topic-specific,
   resolution-independent, subdued behind the cover text, and reproducible.
   Use `--cover-image PATH` when the user supplies or explicitly requests
   bespoke art. If creating raster art, keep it abstract, low-detail,
   text-free, high-resolution, and dark enough for the cover overlay; preserve
   the vector motif as the fallback.
5. Check for Markdown images with `http://` or `https://` sources. The
   renderer warns because Chrome and WeasyPrint may fetch those URLs during
   rendering. Treat that network access as an explicit side effect; use a
   reviewed local image when it is not intended.
6. Audit section references. A visual label such as `§ *Confirm and respond*`
   is not a link; write `[§ *Confirm and respond*](#confirm-and-respond)`.
   Cross-report references need a relative path plus anchor. Treat every
   unlinked `§` warning as blocking for a distribution PDF.
7. Audit executive summaries and "in brief" sections for first-use navigation.
   When a diagnostic term is introduced before its detailed treatment, link it
   directly to the relevant primer or section. Do not assume a nearby general
   primer link is enough for a later, more specific diagnostic claim.
8. Treat blank table cells or prose broken into table rows as a source-structure
   warning, not merely a CSS problem. Compare the Markdown and generated HTML;
   an orphan header plus delimiter can consume the prose that follows as rows.

## 3. Render

Resolve this skill directory from the installed Zentaizo skill, then run:

```bash
python3 <skill-dir>/scripts/render_report_pdf.py \
  sessions/reports/example.md \
  --output sessions/reports/example.pdf \
  --theme auto \
  --fail-on-unlinked-section-refs \
  --fact "256 KB|contiguous allocation required for the veth pair" \
  --fact "97.2%|measured direct-compaction failure rate" \
  --fact "39|lifetime order-6 failures observed"
```

Useful options:

- `--eyebrow TEXT` — report family shown above the cover title.
- `--subtitle TEXT` — override the cover deck; otherwise use the pre-heading
  introduction or first summary paragraph.
- `--organization TEXT` — overrides `organization` frontmatter; defaults to
  neutral `Zentaizo` branding.
- `--cover-note TEXT` — overrides `cover_note` frontmatter or the neutral
  generated-report note.
- `--status TEXT` / `--current-as-of TEXT` — override frontmatter.
- `--cover-image PATH` — use supplied or generated cover art.
- `--engine auto|chrome|weasyprint` — prefer Chrome automatically or select an
  engine explicitly; WeasyPrint output needs its own visual QA.
- `--no-sandbox` — disable the Chrome sandbox only when a constrained
  container or root environment requires it.
- `--render-timeout SECONDS` — bound the renderer process (default: 120).
- `--fail-on-unlinked-section-refs` — reject `§` markers that are not inside
  Markdown links; use this for final distribution renders.
- `--page-break-before SLUG` — repeat for intentional section starts.
- `--columns SLUG` — repeat for compact list-heavy sections.
- `--extra-css PATH` — document-specific table widths or final refinements.
- `--keep-html PATH` — retain the intermediate HTML for inspection.

Use heading slugs printed by `--list-headings` when tuning layout. Keep
document-specific choices in the render command or a small CSS file under
workspace `tmp/`; do not modify the living Markdown just to force pagination.

## 4. Inspect every page

The first PDF is a draft. Render all pages to images and inspect a contact
sheet plus any questionable pages at full size:

```bash
pdfinfo sessions/reports/example.pdf
pdffonts sessions/reports/example.pdf
pdftoppm -jpeg -r 100 sessions/reports/example.pdf tmp/example-page
montage tmp/example-page-*.jpg -thumbnail 360x -tile 4x \
  -geometry +10+10 -background '#d8dee3' tmp/example-contact.jpg
```

Check:

- cover hierarchy, contrast, topic relevance, and fact accuracy;
- table widths, repeated headers, and row breaks;
- code wrapping and inline-code legibility;
- headings stranded at page bottoms;
- sparse pages, orphaned paragraphs, and lonely final-page fragments;
- two-column reading order and font size;
- images, links, footer text, and page numbers.

Refine page breaks, columns, or table widths rather than shrinking the whole
document. Re-render and inspect again.

## 5. Verify content integrity

Extract the final text and confirm that every major section and the ending are
present:

```bash
pdftotext -layout sessions/reports/example.pdf tmp/example.txt
```

Verify that workspace-only frontmatter (`edited_by`, `destined_for`, raw YAML
status fields) is absent from body text, while intended status/date metadata
appears on the cover. Prefer embedded CID TrueType fonts; investigate Type 3
body-font output. Confirm the source Markdown has no renderer-induced diff.

## 6. Preserve the deliverable

Place the PDF beside the report unless the user names another destination.
Check whether PDFs are ignored or untracked. A distribution artifact left
untracked can disappear during cleanup; when repository conventions and user
scope permit, commit it as a separate verified workspace artifact. Report the
PDF path, page count, verification, commit SHA, and push status separately.
