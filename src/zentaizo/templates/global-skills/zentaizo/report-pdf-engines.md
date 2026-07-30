# Report-PDF engine selection

The bundled renderer deliberately uses Markdown → designed HTML/CSS → headless
Chrome/Chromium. This is the best default for Zentaizo living reports because
it supports full-bleed covers, inline SVG, gradients, modern layout, tables,
code blocks, page counters, and fast visual iteration without changing the
authoring format.

## Keep the parser and PDF engine separate

`markdown-it-py` is the Markdown parser, not a PDF renderer. It turns the
living Markdown report into HTML and gives the Zentaizo renderer predictable
tokens that it can classify, decorate, and place inside the publication
template. The final PDF engine then lays out that HTML and CSS:

```text
Markdown → markdown-it-py → designed HTML/CSS → Chrome or WeasyPrint → PDF
```

Changing from Chrome to WeasyPrint does not remove `markdown-it-py`; it changes
only the final layout and PDF-production stage. The `zentaizo[report-pdf]`
extra therefore installs `markdown-it-py`, while Chrome/Chromium and
WeasyPrint are discovered as external executables. This avoids silently
installing a browser or a platform-specific native stack. It also means that a
renderer can be unavailable locally even when the Python extra is installed.

## Chromium versus WeasyPrint

| Concern | Headless Chrome/Chromium | WeasyPrint |
|---|---|---|
| Primary design center | Browser rendering printed to PDF | HTML/CSS paged-media publishing |
| CSS and visual effects | Browser-grade modern CSS, including the grid, flex, gradient, blending, and layered SVG used by the bundled cover | Broad print-oriented CSS, but compatibility and layout details differ from a browser |
| Page composition | Good print CSS and counters; the current CLI exposes a deliberately small print-to-PDF surface | Stronger purpose-built paged media: named pages, `:first`/`:left`/`:right`/`:blank`, margin boxes, bleed, marks, running elements, and footnotes |
| PDF-specific controls | Reliable browser PDF for internal distribution, but few PDF conformance or document-structure controls are exposed by the current toolchain | Bookmarks, links, attachments, forms, tags, XMP metadata, output intents, image optimization, and selectable PDF/A, PDF/UA, and PDF/X variants |
| SVG and fonts | Browser rendering with embedded or system fonts; matches the HTML preview closely | Preserves SVG as vectors and uses Pango/Fontconfig for fonts and text shaping, with font embedding and subsetting |
| Integration model | A bounded subprocess that prints a local `file:` URL; simple when Chrome is already installed | CLI or in-process Python API with page/document objects, a custom URL fetcher, resource controls, and caches |
| Performance | Usually faster for this cover-heavy browser CSS and convenient for repeated local iteration | Its documentation warns that it is often slower; tables spanning many pages can be especially expensive |
| Installation boundary | Requires a system Chrome/Chromium executable | Requires Python packages plus platform-native text-layout and font libraries |
| Reproducibility | Pin the browser build and fonts for strict visual reproducibility | Pin WeasyPrint, Pango, HarfBuzz, Fontconfig, fonts, and related native packages; major WeasyPrint releases may intentionally change rendering |
| Current Zentaizo confidence | Default path, exercised by representative renders and visual QA | Supported as an explicit or automatic fallback, but requires independent visual QA and is not installed in every development environment |

### What WeasyPrint buys

WeasyPrint is the stronger choice when the PDF itself has publication
requirements that are awkward to express through the current Chrome command:

- formal page masters, mirrored margins, running content, bleed, printer marks,
  or footnotes;
- automatic document outlines and PDF attachments or forms;
- archival, accessible, or print-production targets such as PDF/A, PDF/UA, or
  PDF/X;
- a server-side Python service that needs an in-process document API, custom
  resource fetching, or reusable caches.

Selecting a standards variant is not proof of compliance. Validate claimed
PDF/A, PDF/UA, and PDF/X output with an independent conformance checker, and
validate accessibility with assistive-technology testing where it matters.

### What Chromium buys

Chrome remains the better Zentaizo default because the current publication
design was built and visually verified against its browser engine. It renders
the modern layout and cover effects with the same model used for HTML preview,
is already common on author workstations, and keeps iteration to one stylesheet
and one visual-QA path. WeasyPrint would introduce a second compatibility
target, not a drop-in quality upgrade.

The current CLI intentionally invokes either engine as a bounded subprocess.
In `auto` mode it prefers Chrome and warns before falling back to WeasyPrint.
Never treat fallback output as equivalent without rerunning structural,
typographic, and page-by-page visual checks.

### WeasyPrint's native-library boundary

For current WeasyPrint releases, the application-level requirements include
Python 3.10 or newer and packages such as `pydyf`, `cffi`, `tinyhtml5`,
`tinycss2`, `cssselect2`, `Pyphen`, `Pillow`, and `fontTools`. The platform
layer uses Pango for text layout, Fontconfig for font discovery, and HarfBuzz
for shaping and subsetting. On Ubuntu, the documented pip installation path
also needs runtime packages including:

```text
libpango-1.0-0
libharfbuzz0b
libpangoft2-1.0-0
libharfbuzz-subset0
```

Building Python dependencies from source can additionally require development
packages such as `libffi-dev`, `libjpeg-dev`, and `libopenjp2-7-dev`. A
distribution package such as `apt install weasyprint` can resolve this stack,
but it remains platform-managed rather than a pure-Python project dependency.
Modern WeasyPrint no longer directly requires Cairo or GDK-PixBuf; advice that
lists them as mandatory often describes older releases.

This native boundary is manageable, but it expands the reproducibility
contract: record the WeasyPrint and native-library versions, install the exact
fonts, and keep representative visual-regression documents. Neither engine
should receive arbitrary untrusted HTML or unrestricted resource URLs by
default. The bundled path disables raw HTML at Markdown parsing time, reports
remote image fetches, and bounds the renderer subprocess; a service deployment
should also restrict URL protocols or provide a custom fetcher.

## Decision rule

Keep Chrome as the default for existing, visually designed Zentaizo reports.
Choose WeasyPrint deliberately when paged-media primitives, PDF conformance or
accessibility targets, attachments/forms, or Python service integration become
load-bearing. Before promoting it from fallback to co-equal default:

1. pin the Python and native rendering stack;
2. maintain engine-specific CSS where browser and paged-media behavior differs;
3. compare representative short, table-heavy, code-heavy, and long reports;
4. run structural, font, link, conformance, and page-image checks.

Choose another stack when its strengths are load-bearing:

| Stack | Best fit | Tradeoff |
|---|---|---|
| Bundled HTML/CSS + Chromium | Designed internal reports, postmortems, architecture reports, topic-aware covers | Requires visual QA and occasional report-specific CSS |
| Quarto | Executable notebooks, citations, cross-references, figures, and HTML/PDF/Word from one source | Heavier project/toolchain; polished custom covers still need a template |
| Typst | Maintained publication templates, precise typesetting, PDF/A or PDF/UA targets | Native source is Typst rather than Markdown; conversion and custom template work are separate |
| WeasyPrint | Server-side HTML/CSS paged-media pipelines, strong `@page` support, SVG preserved as vectors | Native-library dependencies and rendering differences require pinned-version visual regression tests |
| Pandoc | Rich Markdown parsing and conversion between many formats | A converter, not a design system; pair it with HTML/CSS, LaTeX, Typst, or another PDF engine |

Official references:

- Quarto PDF: <https://quarto.org/docs/output-formats/pdf-basics>
- Quarto format engines: <https://quarto.org/docs/reference/formats/pdf.html>
- Typst PDF export and standards: <https://typst.app/docs/reference/pdf/>
- WeasyPrint installation and native dependencies: <https://doc.courtbouillon.org/weasyprint/latest/first_steps.html>
- WeasyPrint API, PDF features, and CSS support: <https://doc.courtbouillon.org/weasyprint/stable/api_reference.html>
- WeasyPrint performance and service guidance: <https://doc.courtbouillon.org/weasyprint/latest/common_use_cases.html>
- Chrome Headless PDF printing: <https://developer.chrome.com/docs/chromium/headless>
- Pandoc manual: <https://pandoc.org/MANUAL.html>

For a stable organization-wide publishing system, Quarto + Typst is a strong
long-term option if authors are willing to adopt `.qmd` and maintain templates.
For existing Zentaizo Markdown reports whose editorial structure varies, the
bundled HTML/CSS renderer is usually the better cost/quality balance.
