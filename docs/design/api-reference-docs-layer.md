# Workspace README layout tree + an API/reference-docs layer in hierarchical sourcing

## Context

Two gaps surfaced while looking at what `zentaizo create` emits and how the
hierarchy is consulted:

1. **The generated workspace `README.md` never shows the workspace layout.**
   The top-level repo `README.md` has a good "What A Workspace Contains" tree
   (`README.md:126-146`), but `workspace_readme()` (`src/zentaizo/cli.py:103`)
   jumps straight into "First Step" / "Workflow" without ever orienting the
   reader to the directory structure and the *kinds* of knowledge a workspace
   holds.

2. **There is no API / high-level-docs layer between summaries and raw repos.**
   `docs` is already a first-class atlas kind (`cli.py:477`,
   `docs/workspace-format.md:50`), but:
   - `zentaizo fetch` only records `docs` URLs into the lock and explicitly
     defers snapshotting (`cli.py:887`; the lock-schema TODO at
     `workspace-format.md:88`).
   - `AGENTS.md` consultation order is summaries -> repos -> docs, treating docs
     as a tertiary lookup rather than the abbreviated-knowledge layer that sits
     *above* the code.
   - Two real sources of that layer are ignored: (a) **in-repo** API definitions
     already pulled down with the repo (OpenAPI/Swagger files, rustdoc-able
     code, etc.), and (b) **external** polished doc sites (readthedocs / Sphinx /
     MkDocs / GitHub Pages). We neither reuse the external ones nor surface the
     in-repo ones.

This document specs both changes. Part 1 is small and self-contained. Part 2 is
the larger design and carries the open decisions.

The design intent throughout Part 2 follows the repo's standing philosophy
(`AGENTS.md`, and the `zentaizo update` retirement in
`zen-segmend-mesher-template-integration.md`): **keep the CLI thin and
deterministic; push judgment-heavy and conversion work to the AI session.** The
CLI should *fetch and record*; the AI `summarize` step should *interpret and
abbreviate*.

---

## Part 1 — Layout tree in the generated workspace README

### Change

In `workspace_readme()` (`cli.py:103`), insert a `## Layout` section
immediately after the one-line intro (`cli.py:106`) and before `## First Step`.
Reuse the tree from the top-level `README.md`, parameterized on `name`, and
annotate when each artifact appears (some exist at `create` time, some after
`fetch` / `summarize`).

Proposed tree (note `docs/snapshots/` — already reserved in the generated
`.gitignore` at `cli.py:428`, see Part 2):

```text
{name}/
  zentaizo.atlas.json       # human-authored context atlas (you create this first)
  zentaizo.lock.json        # resolved commits/hashes/snapshots (written by `fetch`)
  AGENTS.md                 # agent instructions for this workspace

  repos/                    # fetched source repositories (deepest detail)
  docs/                     # upstream-authored docs: API references, guides, specs
    snapshots/              #   fetched doc-site / spec snapshots (gitignored)
  papers/                   # PDFs and specs (design rationale)
  notes/                    # issue reports, traces, local design notes
  summaries/                # generated hierarchical summaries (start here)
  sessions/
    brainstorming/          # pre-atlas input: transcripts, sketches, inventories
    changes/                # implementation plans, amended with outcomes
    questions/              # dated Q&A logs with researched answers + citations
    debugging/              # dated bug investigations: traces, hypotheses, root cause
```

Add one orienting sentence above the tree naming the level-of-detail spine
(summaries -> docs -> repos -> papers -> notes) so the reader internalizes the
ordering, and keep the existing workflow sections below unchanged.

### Keep in sync

The same tree now lives in three places: top-level `README.md`,
`workspace_readme()`, and `docs/workspace-format.md`. Add a short comment in
`workspace_readme()` pointing at `README.md` as the canonical copy so future
edits stay aligned. (Not worth extracting to a shared constant yet — three
near-identical literals with slightly different framing.)

---

## Part 2 — An API / reference-docs layer

### 2.1 Atlas schema: extend `docs` entries (no new top-level kind)

Reuse the existing `docs` kind rather than inventing `api/`. Add two optional
fields to a `docs` entry:

- **`kind`** — one of `api-reference`, `guide`, `tutorial`, `spec`,
  `changelog`. Unset = generic doc (today's behavior). Drives consultation
  ordering (2.5) and summarize provenance (2.6).
- **A source discriminator** distinguishing *external* from *in-repo* docs:
  - External site: keep today's `url` field.
  - In-repo artifact (already fetched under `repos/`): `repo` (name of a repo
    source) + `path` (path within that repo), e.g. an `openapi.yaml` checked
    into a service repo.

Example:

```json
"docs": [
  {
    "name": "shortener-api-site",
    "kind": "api-reference",
    "url": "https://shortener.readthedocs.io/en/stable/",
    "description": "Public Sphinx API reference"
  },
  {
    "name": "shortener-openapi",
    "kind": "spec",
    "repo": "shortener-api",
    "path": "openapi/openapi.yaml",
    "description": "OpenAPI 3.1 spec living in the API repo"
  }
]
```

`validate` gains a check: a `docs` entry must have exactly one of `url` or
(`repo` + `path`); `kind`, if present, must be in the allowed set; a `repo`
reference must name an existing repo source.

### 2.2 Discovery — what curate-atlas should actively probe

Most of this is judgment work, so it belongs in `skills/curate-atlas.md`
(AI-driven), with an optional thin CLI helper for the deterministic parts. When
inventorying each repo, the AI should look for:

- **External doc sites:** `.readthedocs.yaml` / `readthedocs.yml`; README badges
  or links to `*.readthedocs.io` / GitHub Pages; `pyproject.toml`
  `[project.urls]` `Documentation`; `docs/` containing `conf.py` (Sphinx) or
  `mkdocs.yml`.
- **In-repo API specs:** `openapi.{yaml,json}`, `swagger.{yaml,json}`,
  `**/openapi*.{yaml,json}`; a FastAPI/Flask app exposing `/openapi.json`;
  GraphQL `schema.graphql`; protobuf `.proto`.
- **Code-level doc generators available** (informs 2.7): Rust crate (`cargo
  doc`/rustdoc), Python package (`pdoc`), TS (`typedoc`), Go (`go doc`).

Optional CLI helper `zentaizo discover-docs [workspace]`: scans already-fetched
`repos/` for the in-repo patterns above and prints candidate `docs` entries for
the human/AI to paste into the atlas. Pure read-only scan, no network — stays
within the thin-CLI rule. (Defer if we want curate-atlas to own all of it.)

### 2.3 Fetching/snapshotting external doc sites — component choice

This is the part that needs an external component, and the main design tension.
Researched options (sources at bottom):

| Approach | Output | New dependency | Notes |
|---|---|---|---|
| **RTD downloadable build** | HTMLZip / PDF / ePub | none (HTTP GET) | Read the Docs exposes offline builds at predictable `/_/downloads/...` URLs. Cheapest faithful snapshot for the very common RTD case. |
| **`wget --mirror`** | HTML tree | none (ubiquitous) | Faithful, but HTML is token-heavy and needs link rewriting; conversion deferred to AI. |
| **Crawl4AI** | LLM-ready Markdown | heavy (Python + Playwright/headless browser) | Best markdown, but a large dep footprint that cuts against the thin-CLI rule. |
| **markdowner** (supermemory) | Markdown | self-hosted service or hosted API | Compact markdown; needs a running service. |
| **Firecrawl** | Markdown | paid hosted API / self-host | Cleanest markdown; external paid dependency, network egress of source URLs. |

**Recommendation:** make the doc fetcher a small pluggable interface with a
**zero-dependency default**, and *defer markdown conversion to the AI summarize
step* (which already runs an AI, so HTML->markdown is free there). Concretely:

1. If the URL is a Read the Docs project, fetch its HTMLZip offline build by
   convention and unzip into `docs/snapshots/<name>/`.
2. Otherwise, `wget --mirror` (or `urllib`-based bounded crawler) the doc URL
   into `docs/snapshots/<name>/`, capped by depth/page-count/same-host.
3. Record a content hash + `fetched_at` + `fetcher` in the lock.
4. Leave a richer markdown-converter (Crawl4AI / Firecrawl / markdowner) as an
   **opt-in** selected via config/env (`docs.fetcher`), not a hard dep.

Put this behind a **separate subcommand `zentaizo fetch-docs`**, not inside
`zentaizo fetch`. Rationale: cloning pinned git repos and crawling arbitrary
external websites are different risk/latency/network profiles; doc snapshotting
should be explicit and opt-in, and `fetch` stays fast and predictable.

### 2.4 In-repo API specs — already local, just surface them

For `kind: spec` / in-repo `api-reference` entries, the artifact is *already
present* under `repos/<repo>/<path>` after `fetch`. No snapshotting needed.
`fetch-docs` should:

- Verify the `repo`+`path` resolves to a file in the fetched tree; record its
  content hash in the lock so staleness is detectable.
- Optionally render OpenAPI/Swagger -> Markdown into `docs/snapshots/<name>.md`.
  Conversion tools researched: Widdershins, swagger-markdown (both Node),
  `openapi-to-md` (zero-dep Python). Prefer the Python one *if* we convert in
  the CLI; otherwise skip and let summarize read the raw spec (OpenAPI YAML is
  already fairly LLM-legible). **Recommendation:** skip CLI conversion v1; the
  raw spec + AI summarize is enough.

### 2.5 Consultation order (AGENTS.md)

Update `## Source Consultation` (`cli.py:203-211`) from
`summaries -> repos -> docs -> papers -> notes` to:

1. `summaries/` — big picture.
2. `docs/` — **upstream-authored API references and guides, when present**
   (prefer `kind: api-reference`/`spec`). The abbreviated, authoritative middle
   layer.
3. `repos/` — implementation details / ground truth.
4. `papers/` — design rationale.
5. `notes/` — traces, issue reports, local decisions.

State the principle explicitly: prefer upstream-authored docs over
AI-regenerated summaries when both exist and agree; fall to `repos/` as ground
truth on any conflict.

### 2.6 `summarize` reuse (cli.py:894)

When a `docs` snapshot exists for a source, the summarize prompt should instruct
the AI to **summarize from the snapshot** (and cite it) rather than
re-deriving from code — the "reuse, don't regenerate" property. Record
provenance in `summaries/sources/<name>.md` (e.g. a `source: docs-snapshot` vs
`source: code` marker) so a reader knows whether a summary is upstream-grounded.

### 2.7 Generated (code-derived) API docs — where they live

For repos with *no* upstream site and *no* in-repo spec, code-level API docs can
be generated (rustdoc/pdoc/typedoc/godoc). **Recommendation:** keep generation
out of the CLI (toolchain sprawl), and place any AI- or tool-generated API
overview in `summaries/` (e.g. `summaries/sources/<name>.md` marked `kind:
api-reference`), **not** in `docs/`. This preserves the invariant that `docs/`
is *upstream-authored* and `summaries/` is *workspace-generated*. Document the
manual `cargo doc` / `pdoc` path as optional guidance in curate-atlas.

### 2.8 Lock + workspace-format docs

- Fill the deferred docs/papers lock schema (`workspace-format.md:88`): per doc
  source record `url` or (`repo`,`path`), snapshot path under
  `docs/snapshots/`, content hash, `fetched_at`, and `fetcher`/converter used.
- Document `kind`, the external-vs-in-repo discriminator, and the
  `docs/snapshots/` layout in `workspace-format.md`.

---

## Open decisions (need a call before building)

1. **Reuse `docs` kind vs new `api/` kind.** Spec assumes reuse + `kind` field.
   (Recommended: reuse.)
2. **CLI fetcher dependency.** Zero-dep default (RTD build / wget) with opt-in
   markdown converter, vs commit to one markdown crawler (Crawl4AI/Firecrawl)
   for quality. (Recommended: zero-dep default, conversion at summarize.)
3. **`fetch-docs` separate subcommand vs folding into `fetch`.** (Recommended:
   separate, opt-in.)
4. **Generated API docs home: `summaries/` vs synthetic `docs/`.** (Recommended:
   `summaries/`, keep `docs/` upstream-only.)
5. **CLI-side OpenAPI->Markdown conversion in v1 or skip.** (Recommended: skip;
   raw spec + AI.)

## Suggested build order

1. Part 1 (README tree) — small, ship independently.
2. Atlas schema + `validate` (2.1) and `discover-docs` read-only scan (2.2).
3. AGENTS.md reorder + summarize provenance (2.5, 2.6) — pure prompt/text, no
   network.
4. `fetch-docs` with zero-dep default + lock schema (2.3, 2.4, 2.8).
5. curate-atlas probing guidance (2.2) + optional converter plumbing (2.3).

## Research sources

- Offline doc mirroring: [HTTrack](https://www.httrack.com/),
  [wget mirroring guide](https://dev.to/rijultp/how-to-use-wget-to-mirror-websites-for-offline-browsing-48l4),
  [Read the Docs offline/downloadable formats](https://docs.readthedocs.com/platform/latest/downloadable-documentation.html).
- OpenAPI/Swagger -> Markdown:
  [Widdershins](https://mermade.github.io/widdershins/ConvertingFilesBasicCLI.html),
  [swagger-markdown](https://github.com/syroegkin/swagger-markdown),
  [openapi-to-md (PyPI)](https://pypi.org/project/openapi-to-md/).
- Code-level / multi-language API docs:
  [OpenAPI Generator](https://github.com/OpenAPITools/openapi-generator),
  [Fern](https://buildwithfern.com/learn/sdks/generators/go/quickstart),
  [Rustdoc guide](https://apidog.com/blog/rustdoc/).
- Website -> Markdown for LLMs:
  [Firecrawl](https://www.firecrawl.dev/),
  [markdowner](https://github.com/supermemoryai/markdowner),
  [Crawl4AI](https://www.freecodecamp.org/news/how-to-turn-websites-into-llm-ready-data-using-firecrawl/).
