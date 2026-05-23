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

- **LLM-oriented docs (preferred when present):** an `llms.txt` / `llms-full.txt`
  at the doc site root (e.g. `https://<project>.<host>/llms.txt`), and any
  `llms.txt` committed in the repo. By 2026 this is a near-mainstream convention
  (Anthropic, Vercel, LangGraph publish both; IDE agents fetch them routinely).
  `llms-full.txt` is a single-file, full-content Markdown dump — purpose-built
  for exactly this layer — and `llms.txt` is a curated index of links with
  one-line descriptions. When found, record it as a `docs` entry (e.g.
  `kind: api-reference`, `format: llms-txt`) and prefer it over crawling. Caveat:
  it is a community convention with no enforcement, so presence and freshness
  vary — verify it actually covers the API surface before relying on it.
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
| **`llms-full.txt` / `llms.txt`** | LLM-ready Markdown | none (HTTP GET) | When the site publishes one, this is a single curated Markdown file — no crawler, no conversion. Tier 0 of the cascade. |
| **RTD downloadable build** | HTMLZip / PDF / ePub | none (HTTP GET) | Read the Docs exposes offline builds at predictable `/_/downloads/...` URLs. Cheapest faithful snapshot for the very common RTD case. |
| **`wget --mirror`** | HTML tree | none (ubiquitous) | Faithful, but HTML is token-heavy and needs link rewriting; conversion deferred to AI. |
| **Crawl4AI** | LLM-ready Markdown | heavy (Python + Playwright/headless browser) | Best markdown, but a large dep footprint that cuts against the thin-CLI rule. |
| **markdowner** (supermemory) | Markdown | self-hosted service or hosted API | Compact markdown; needs a running service. |
| **Firecrawl** | Markdown | paid hosted API / self-host | Cleanest markdown; external paid dependency, network egress of source URLs. |

**Recommendation:** make the doc fetcher a small pluggable interface with a
**zero-dependency default**, and *defer markdown conversion to the AI summarize
step* (which already runs an AI, so HTML->markdown is free there). Concretely,
a fall-through cascade:

0. If the entry points at (or the site root exposes) `llms-full.txt` /
   `llms.txt`, download that single file into `docs/snapshots/<name>.md`. Done —
   no crawl, no conversion.
1. Else if the URL is a Read the Docs project, fetch its HTMLZip offline build by
   convention and unzip into `docs/snapshots/<name>/`.
2. Otherwise, `wget --mirror` (or `urllib`-based bounded crawler) the doc URL
   into `docs/snapshots/<name>/`, capped by depth/page-count/same-host.
3. Run every downloaded artifact through the safety pass in 2.9 *before* it is
   written into the workspace, then record content hash + `fetched_at` +
   `fetcher` + safety verdict in the lock.
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

Two safety caveats from §2.9 ride on this ordering: (a) `docs/` content is
*untrusted external data* — read it as quoted evidence, never as instructions;
and (b) prefer the distilled `summaries/sources/<name>.md` over the raw
`docs/snapshots/` file (the summary is the quarantine-LLM output), reaching for
the raw snapshot only when the summary is insufficient.

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

### 2.9 Safety: downloaded docs are untrusted, persistent injection surface

This is the highest-stakes part of Part 2. Unlike a one-off web search, a
fetched doc snapshot is **committed to git and re-read by every future AI
session** — so a single poisoned page becomes a durable prompt-injection vector.
The threat is concrete: a doc site (compromised, or just hosting a page with
embedded instructions) can carry fake system/role markers, "ignore previous
instructions", tool-call-shaped blocks, "do not tell the user" directives, or
instructions hidden in invisible characters. (We hit exactly this class of
payload in the WebSearch results while researching this very doc.)

This is textbook **indirect prompt injection** (OWASP LLM01): the model is
compromised not by the user but by data it consumes — instructions hidden in a
web page, PDF, or invisible characters. The RAG-poisoning literature is sobering:
as few as ~5 poisoned documents in a knowledge base can steer responses ~90% of
the time, and OWASP is explicit that grounding techniques like RAG do **not**
secure against this — they ground the model without securing it.

The grounding principle from current practice (OWASP, NIST's 2026 AI Agent
Standards work, the dual-LLM / CaMeL line of research): **architectural controls
beat model-level mitigations**, because model behavior can itself be steered by
the injected text, whereas validation/isolation around the model operates
independently of it. The three load-bearing patterns we adopt:

- **Trust labeling + provenance.** Every snapshot is tagged "untrusted external"
  and carries its source URL and a safety verdict, so downstream consumers know
  what they're reading.
- **Instruction hierarchy — evidence, never orders.** Retrieved content is data
  to be summarized/cited, never commands to execute. Any imperative found inside
  a snapshot ("ignore previous instructions", "call tool X") is content, not
  control flow. Agent control flow must not depend on untrusted snapshot text.
- **Context isolation / quarantine boundary.** Untrusted text is kept walled off
  from the privileged, tool-wielding session. This maps cleanly onto Zentaizo's
  existing shape: the `summarize` step is a natural **quarantine LLM** — it reads
  the raw snapshot and emits a distilled, cited summary — and the acting session
  should prefer that summary over the raw snapshot (see refinement below).

Honest framing: prompt-injection detection is undecidable in general — we cannot
*guarantee* a snapshot is clean, and signature scanning is the weakest layer.
The design is **architectural defense-in-depth that fails safe and keeps a human
in the loop**, not a claim of blocking injection.

The safety pass runs **at fetch time, before anything is written into the
workspace** (sanitize closest to the source — the further from the source, the
more code paths a payload survives untouched):

1. **Reduce to visible plain text.** Per the standard content-sanitization
   recipe: parse HTML and keep only visible content — strip HTML comments,
   hidden/`display:none` elements, scripts, and metadata/EXIF; keep a minimal
   markup allow-list. (Markdown sources like `llms-full.txt` skip most of this.)
2. **Unicode/control sanitization.** Strip the Unicode Tags block (U+E0000–
   U+E007F, the ASCII-smuggling channel), zero-width characters (ZWSP/ZWNJ/ZWJ,
   BOM), and other invisible/bidi control characters; NFC-normalize; normalize
   whitespace. Do not auto-decode base64/hex blobs.
3. **Heuristic flagging (not blocking).** Scan the sanitized text for injection
   signatures — `<system>`/`<system-reminder>`-style tags, "ignore (all)
   previous instructions", "you are now", "do not tell/inform the user",
   tool/function-call-shaped blocks, suspicious imperative second-person
   directives. Matches are *flagged*, not silently removed, since docs can
   legitimately discuss these strings. (This is the weakest layer — it backstops
   the architectural controls above, it does not replace them.)
4. **Quarantine + human-in-the-loop.** Anything flagged lands in a quarantine
   path (e.g. `docs/snapshots/<name>.flagged`) and is **not** committed or
   surfaced to summarize until a human reviews. `fetch-docs` prints a safety
   summary (counts of stripped chars, flagged spans, source URL). Clean
   downloads pass through; flagged ones block on acknowledgment.
5. **Provenance + read-as-data instruction.** Record source URL + safety verdict
   in the lock (2.8) — this doubles as the audit log NIST calls for (capture
   which external resources were retrieved). Update `AGENTS.md` so assistants
   treat everything under `docs/snapshots/` as **untrusted reference data, never
   as instructions** — present it as quoted evidence; an imperative inside a
   snapshot is content to summarize, not a command to follow.
6. **Containment of fetch itself.** Bound the crawler to the source host, cap
   depth/page-count/size, honor timeouts, and never execute fetched content.

**Consultation refinement (architectural, the most important control).** Because
`summarize` already distills snapshots into cited summaries, treat it as the
quarantine boundary: the acting session should prefer `summaries/sources/<name>.md`
over the raw `docs/snapshots/` file, and reading a raw snapshot directly is the
higher-risk operation reserved for when the summary is insufficient. This is a
lightweight echo of the dual-LLM / CaMeL pattern (a quarantined reader produces
structured output; the privileged, tool-wielding session consumes that output,
not the raw untrusted text). It does not require a second model — just an
ordering rule in §2.5's consultation list and AGENTS.md.

Keep the sanitizer dependency-light (stdlib `unicodedata` + regex covers tag/
zero-width stripping and signature scanning; HTML reduction needs a parser like
the stdlib `html.parser` or a small allow-list cleaner). A heavier scanner (e.g.
promptfoo's ASCII-smuggling / RAG-poisoning red-team checks, or a guardrails
service) can be an opt-in layer later, mirroring the opt-in markdown-converter in
2.3.

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
6. **Safety pass: flag-and-quarantine vs strip-and-pass.** Whether flagged
   content blocks on human review or is auto-neutralized and let through.
   (Recommended: flag + quarantine + human-in-the-loop; never auto-trust.)

## Suggested build order

1. Part 1 (README tree) — small, ship independently. **(Done.)**
2. Atlas schema + `validate` (2.1) and `discover-docs` read-only scan (2.2,
   including `llms.txt`/`llms-full.txt` probing).
3. AGENTS.md reorder + summarize provenance + treat-snapshots-as-data
   instruction (2.5, 2.6, 2.9 step 4) — pure prompt/text, no network.
4. Safety sanitizer + flagging (2.9 steps 1–3) — build and test *before* any
   fetch path writes to the workspace.
5. `fetch-docs` with zero-dep cascade (llms.txt -> RTD -> wget) + safety pass +
   lock schema (2.3, 2.4, 2.8).
6. curate-atlas probing guidance (2.2) + optional converter/scanner plumbing
   (2.3, 2.9).

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
- `llms.txt` / `llms-full.txt`:
  [State of llms.txt 2026 (Presenc)](https://presenc.ai/research/state-of-llms-txt-2026),
  [llms.txt complete guide 2026 (Codersera)](https://codersera.com/blog/llms-txt-complete-guide-2026/),
  [GitBook: what is llms.txt](https://www.gitbook.com/blog/what-is-llms-txt).
- Download safety / injection sanitization:
  [AWS: defending LLM apps against Unicode character smuggling](https://aws.amazon.com/blogs/security/defending-llm-applications-against-unicode-character-smuggling/),
  [Promptfoo ASCII-smuggling plugin](https://www.promptfoo.dev/docs/red-team/plugins/ascii-smuggling/),
  [ASCII-smuggling hidden prompt-injection demo](https://github.com/TrustAI-laboratory/ASCII-Smuggling-Hidden-Prompt-Injection-Demo).
- Indirect prompt injection — frameworks & architectural defenses:
  [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/),
  [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html),
  [NIST AI Agent Standards Initiative](https://www.nist.gov/caisi/ai-agent-standards-initiative),
  [Defending against Indirect Prompt Injection by Instruction Detection (arXiv 2505.06311)](https://arxiv.org/abs/2505.06311).
