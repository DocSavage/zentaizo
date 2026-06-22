---
created: 2026-06-21
status: brainstorming
edited_by:
  - 2026-06-21  Bill Katz, Claude Opus 4.8 (1M context, relocated from the zen-ACG workspace)
---

# fetch-docs: clean web extraction via optional external components

_Brainstorm — a design proposal to discuss before changing `fetch-docs`, not
itself the change._

## Source

- Origin: discovered in a downstream Claude Code workspace (`zen-ACG`) while
  snapshotting VAST articles with `zentaizo fetch-docs`; relocated here so the
  note lives with zentaizo's own design trail rather than a consumer workspace.
- Author / system: Bill Katz (direction) + Claude Opus 4.8 (analysis/proposal).
- Source date: 2026-06-21.
- Evidence: reproducible directly from this repo's `src/zentaizo/cli.py` (the
  tier walk-through below); the originating run and its downstream resolution
  live in the zen-ACG workspace's git history.

## Problem

### What `fetch-docs` does today

`zentaizo fetch-docs` snapshots every atlas `docs` source into `docs/snapshots/`,
running each through a safety pass before writing. The fetch path is a
**bespoke stdlib baseline** (`src/zentaizo/cli.py`):

- `_fetch_external_doc` (~`cli.py:1630`) is a tiered cascade:
  - **Tier 0 — llms.txt:** `_llms_candidates(url)` probes `{host}/llms-full.txt`
    then `{host}/llms.txt`; if either returns non-empty text it is used verbatim.
  - **Tier 2.5 — single page:** `urllib` GET of the URL, then a naive
    HTML→text strip in the safety pass. The comment notes "no full-site crawl in
    the stdlib baseline; mirroring belongs to the optional `[docs-rich]` extra."
  - **Tier 4 — reference-only** on fetch error.
- Safety: `safety.sanitize(...)` (stdlib) plus an optional `llm-guard` deep scan
  behind the **`docs-scan`** extra (the only extra actually defined in
  `pyproject.toml`).

Note: the `[docs-rich]` extra is *referenced in a comment but never defined* —
the "rich" extraction path is aspirational, so today every page falls back to
the naive baseline.

### The bug (evidence)

Running `fetch-docs` over a real atlas:

- Two page-specific `kb.vastdata.com` doc entries each produced a
  **576,201-byte, byte-identical** snapshot (`cksum` matched). It was not either
  page — it was the whole VAST knowledge base, because the site publishes
  `kb.vastdata.com/llms-full.txt` and Tier 0 returns that *site-wide* dump for
  **any** URL on the host. Two page-specific entries → the same whole-KB file,
  mislabeled.
- A separate article (The Next Platform) fetched via single-page and *does*
  contain the article, but the text is wrapped in site chrome — nav menus,
  "Jump to main content", topic lists, ads/boilerplate — because the baseline
  strips tags without extracting the main content region.

The downstream workspace worked around it by hand (drop the mislabeled dumps,
revert those lock entries to `reference-only`), but that is fragile —
**re-running `fetch-docs` re-creates the dumps**, because the root cause here is
unchanged.

### The general problem

Fetching a web page and producing *clean* content — main article only, no nav,
ads, cookie banners, related-links, or JS-injected cruft — is a hard,
well-studied problem (readability/boilerplate detection, DOM main-content
extraction, JS rendering, paywalls). A few hundred lines of stdlib HTML
stripping cannot match it, and trying to grow our own into a real extractor is a
poor use of effort: it is a maintenance sink that mature, dedicated libraries
already solve far better.

## Direction

> Rather than create our own bespoke system, more thoroughly involve optional
> external components.

Concretely: keep the **zero-dependency stdlib baseline as the always-present
fallback** (offline, minimal installs, and a safe default), but **delegate the
real work to mature external extractors, installed as optional extras**. The
architecture already leans this way — `docs-scan` (llm-guard) is optional, and
the code anticipates a `docs-rich` extra. Make that real and pluggable rather
than hand-rolling extraction.

## Proposed changes

### 1. Immediate, no-dependency fix to the llms tier

Stop Tier 0 from returning a site-wide dump for page-specific entries. Options
(not mutually exclusive):

- Only treat llms.txt as the source when the **entry URL itself** is an
  `llms.txt` / `llms-full.txt` (i.e. `_llms_candidates` returns `[url]` only in
  that case; otherwise return `[]`).
- Or make llms a **per-entry opt-in** atlas field (e.g. `prefer_llms: true`) so a
  human decides when a site-wide index is the intended artifact.
- Demote llms below page extraction so it is only a last resort before
  reference-only.

This alone stops the mislabeled whole-site dumps and is safe to ship without new
dependencies.

### 2. Define a pluggable extraction backend (`docs-rich` / `docs-extract` extra)

Introduce a small backend interface — `extract(html, url) -> (markdown, metadata)`
— with the stdlib strip as the default implementation, and a richer
implementation enabled when the extra is installed. Primary candidate:

- **trafilatura** (local, no extra network): main-content extraction with
  boilerplate/comment removal and **Markdown output** + metadata; well
  maintained; good default.
- Alternative/combination: **readability-lxml** (Mozilla Readability port → main
  article HTML) + **markdownify** or **html2text** for HTML→Markdown.

Record the backend + version in the lock alongside the existing `fetcher` field
for provenance.

### 3. Optional JS-render and hosted-reader backends (opt-in, public-only)

For JS-heavy pages the baseline (and even trafilatura on raw HTML) misses:

- **Playwright** (heavier extra) to render, then run the same extractor.
- A **hosted reader** backend — e.g. **Jina AI Reader** (`r.jina.ai/<url>`) or
  **Firecrawl** — that returns clean Markdown directly.

Hosted readers **send the target URL to a third party**, so they must be
strictly opt-in and **never used for internal or gated hosts** (anything
internal or behind auth — a customer KB portal, an institutional cluster). Gate
by an allowlist or explicit per-entry/per-host flag.

### 4. Keep the safety pass on every path

Extraction is orthogonal to safety. Whatever backend produces the text, it still
flows through `safety.sanitize(...)` and the optional `llm-guard` deep scan.
External extractors *reduce* the injection surface (they drop scripts and hidden
text) but do not replace the guard — fetched docs remain untrusted input.

### Resulting cascade (sketch)

```
URL is itself an llms.txt/llms-full.txt        -> use directly (legit index)
elif hosted-reader enabled AND host allowlisted -> Jina/Firecrawl -> markdown
elif docs-rich extra installed                  -> fetch (+Playwright?) -> trafilatura/readability -> markdown
else                                            -> stdlib single-page strip (today's baseline)
else                                            -> reference-only
# every produced artifact -> safety.sanitize (+ optional llm-guard) -> write
# REMOVED: the current Tier-0 site-wide llms-full.txt grab for arbitrary pages
```

## Candidate components (trade-offs)

| Component | Role | Local/Hosted | Notes |
|---|---|---|---|
| trafilatura | main-content extraction → Markdown | local | strong default; metadata; maintained |
| readability-lxml + markdownify | article HTML → Markdown | local | Readability port; pair with a converter |
| jusText / boilerpy3 / Goose3 | boilerplate removal | local | older; fallbacks, not primary |
| Playwright | JS render before extraction | local (browser dl) | heavy; only for JS-heavy pages |
| Jina AI Reader (`r.jina.ai`) | URL → clean Markdown | hosted | easiest; **sends URL out**; public only |
| Firecrawl | crawl/extract → Markdown | hosted (API key) | richer; **sends URL out**; public only |

## Safety & privacy considerations

- **Untrusted content stays untrusted.** No backend bypasses the safety pass;
  flagged output is still quarantined to `*.flagged.*`, which the default
  `create_workspace` `.gitignore` excludes while committing clean snapshots.
- **Egress/privacy.** Local extractors only fetch the page the workspace already
  intends to fetch. Hosted readers add a third party — opt-in, public hosts only.
- **Determinism/provenance.** Different backends yield different text; record the
  backend + version in the lock so a snapshot's origin is auditable, and so a
  backend change is a visible diff rather than silent drift.
- **Graceful degradation.** Missing extras must never fail a run — fall back to
  the stdlib baseline and record which backend was used.

## Open questions

- Default backend when `docs-rich` is installed: trafilatura alone, or
  trafilatura with a readability fallback?
- Is a hosted-reader backend wanted at all, given the highest-value docs are
  often gated/internal? Possibly skip hosted entirely and rely on local
  extraction + Playwright.
- Should the immediate llms fix (#1) ship on its own first (no deps, stops the
  active bug), with the pluggable backend (#2+) as a follow-up?
- For sites that publish a useful site-wide `llms-full.txt`, do we want a
  *separate, explicit* doc entry (e.g. `<site>-llms-full`) rather than silently
  attaching the whole index to a page-specific entry?
- Where does extraction config live — atlas per-entry fields, a workspace-level
  `fetch` config block, or CLI flags?
