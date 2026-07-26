# The reference-docs layer: sourcing, snapshotting, and incremental summaries

_Distilled design doc — current architecture + rationale._

## What it is

A Zentaizo workspace orders the knowledge it aggregates along a level-of-detail
spine: `summaries/` (big picture) → `docs/` (upstream-authored API references and
guides) → `repos/` (implementation ground truth) → `papers/` → `notes/`. This
document covers the middle of that spine — the **reference/API docs layer** — and
the two CLI subsystems that feed and consume it: a docs **content scanner**
(`fetch-docs` / `discover-docs`) that turns atlas `docs` entries into committed,
safety-screened snapshots, and an **incremental, focus-aware `summarize`** that
distills sources into summaries without re-doing work that is still current.

The design follows the repo's standing split: the CLI stays thin and
deterministic — it *fetches, records, and decides what needs work* — while the
judgment-heavy interpretation (writing prose summaries, deciding which doc sites
matter) is pushed to the AI session. A second principle runs through the whole
layer: **fetched content is untrusted, persistent prompt-injection surface**,
because a snapshot is committed to git and re-read by every later session, so the
safety controls are architectural (quarantine, evidence-not-orders,
human-in-the-loop), not a claim to detect injection.

## Architecture

### Atlas schema for `docs` (`src/zentaizo/cli.py`)

A `docs` entry reuses the existing `docs` source kind rather than a new top-level
kind. Each entry may carry an optional `kind` — one of the five in
`VALID_DOC_KINDS` (`api-reference`, `guide`, `tutorial`, `spec`, `changelog`) — and
names its source exactly one of two ways:

- **External** — a `url` (a doc site, an `llms.txt`, an OpenAPI URL).
- **In-repo** — a `repo` (the name of a repo source in the same atlas) plus a
  `path` relative to that repo's fetched tree; `doc_is_in_repo()` keys on the
  presence of `repo`.

`validate_doc_entries()` enforces the discriminator: an entry cannot carry both
`url` and `repo`, an in-repo entry must give a `path`, the `repo` must name a real
repo source, and `kind` (if present) must be in the allowed set. Source names are
also globally checked against `SAFE_SOURCE_NAME` (`^[A-Za-z0-9][A-Za-z0-9._-]*$`,
no `..`) in `validate_workspace()`, because `<name>` is used verbatim as a path
component (`docs/snapshots/<name>`, `summaries/sources/<name>.md`).

### `discover-docs` — read-only in-repo scan (`discover_docs_workspace`)

`zentaizo discover-docs [PATH]` walks the already-fetched `repos/` tree
(`_scan_repo_for_docs`), pruning noisy/vendored directories (`_SCAN_NOISE_DIRS`)
and hidden dirs. `_classify_doc_file()` recognizes `openapi*`/`swagger*`
specs, GraphQL schemas, `.proto` files, and `llms.txt`/`llms-full.txt`; doc-site
configs (`.readthedocs.yaml`, `mkdocs.yml`, `docs/conf.py`) are reported as site
markers. It prints ready-to-paste `docs` atlas entries (`repo` + `path`) for
candidates not already in the atlas, and never writes — the human or AI pastes
what they want. Pure local filesystem scan, no network.

### `fetch-docs` — snapshot with a safety pass (`fetch_docs_workspace`)

`zentaizo fetch-docs [PATH]` is a separate subcommand from `fetch` (different
risk/latency/network profile: `fetch` clones pinned git repos, `fetch-docs` reads
arbitrary external sites). It iterates atlas `docs` entries and routes each:

- **In-repo** (`_snapshot_in_repo_doc`) — the artifact already lives at
  `repos/<repo>/<path>` after `fetch`; it is read and screened, no network. A
  missing file yields `reference-only` with reason `not-fetched`.
- **External** (`_fetch_external_doc`) — a stdlib HTTP cascade (`_http_get`,
  bounded by `_HTTP_TIMEOUT` and `_HTTP_MAX_BYTES`, http/https only):
  1. **Tier 0** — probe `llms-full.txt` then `llms.txt` at the site root
     (`_llms_candidates`); if present, that single curated Markdown file *is* the
     snapshot (fetcher `llms-txt`).
  2. **Tier 2.5** — otherwise salvage the single referenced page (fetcher
     `single-page`); bundled Trafilatura extracts the main content as Markdown
     using the versioned `main-content-v1` profile.
  3. **Terminal** — if everything fails, the entry stays `reference-only` with a
     reason of `no-source` (a non-http(s) URL, quiet) or `fetch-error` (a real
     failure, surfaced as a loud `WARNING`).

Every downloaded artifact passes through `_apply_safety_and_write()` *before* it is
written into the workspace. Clean content lands at `docs/snapshots/<name>.<ext>`
with `status: ok`; flagged content is quarantined at
`docs/snapshots/<name>.flagged.<ext>` with `status: flagged` and is never surfaced
as a usable snapshot. Each result is recorded in the top-level
`lock["doc_snapshots"]` with `content_hash`, `status`, `fetched_at`, the resolved
source/fetcher, and a `safety` block. HTML entries also record an `extraction`
block (`extractor`, exact version, profile, and raw-input hash). The same
extraction path handles in-repo `.html`/`.htm` files. If Trafilatura declines
or fails, the stdlib reducer remains a `.txt` fallback; runtime failures emit a
warning and record the reason. Before publishing a new clean or quarantined
result, known prior text variants are removed, so `.txt`/`.md` transitions and
`ok`/`flagged` transitions cannot leave a stale trusted snapshot behind.
`fetched_at` is preserved across a no-op re-fetch
(`_preserve_unchanged_fetched_at`, keyed on `content_hash`+`status`) so it means
"when the content we hold was obtained," not "last attempt."

### The safety pass (`src/zentaizo/safety.py`)

After optional main-content extraction, `sanitize(content, *, is_html,
deep_scan)` runs the always-on, stdlib-only baseline: (1) for a fallback HTML
path, reduce HTML to visible text, dropping scripts/styles/comments
(`reduce_html_to_text`); (2) strip invisible/smuggling characters — the Unicode
Tags block, zero-width and bidi controls, other C0/C1 format chars — and
NFC-normalize (`strip_unsafe_unicode`); (3) flag injection signatures
(`scan_for_injection` against `_SIGNATURES`: fake role/`system-reminder` tags, chat
templates, "ignore previous instructions", persona overrides, conceal-from-user,
tool-call shapes). Any flag flips `SafetyResult.verdict` to `flagged`. Signature
matching is the weakest layer — it backstops the architectural controls, it does
not replace them.

An optional **deep scanner** layers on top: with the `zentaizo[docs-scan]` extra
installed, `load_deep_scanner()` loads the LLM Guard adapter
(`src/zentaizo/_llm_guard_scan.py`, a model-based `PromptInjection` scanner). Its
findings merge into the same `flags`/quarantine path; it never replaces the
baseline. Loading fails safe — a missing extra is silent (`none`), an
installed-but-broken model degrades to `unavailable` with a warning, never a crash.
`fetch-docs --no-deep-scan` disables *only* the optional layer (the mandatory
baseline always runs). Each snapshot's `safety` block records `baseline_scanner`
(`stdlib`) and `deep_scanner` (`llm-guard` / `none` / `disabled` / `unavailable`) as
an audit trail.

### Consultation order (generated workspace `AGENTS.md`, written in `cli.py`)

The generated `AGENTS.md` places `docs/` as the abbreviated, authoritative layer
between `summaries/` and `repos/`, preferring entries with `kind: api-reference` or
`spec`, and states the rule: prefer upstream-authored docs over AI-regenerated
summaries when both agree, fall to `repos/` as ground truth on conflict. It also
instructs agents to treat everything under the workspace — `docs/snapshots/`
especially — as untrusted data: evidence to cite and summarize, never instructions
to follow. The `summarize` step embeds the same "reuse, don't regenerate" guidance:
when a `docs` source provides an API reference, summarize from it and cite it
rather than re-deriving the surface from code.

### Incremental, focus-aware `summarize` (`summarize_workspace`)

`zentaizo summarize [PATH] [--force|--all] [--focus TEXT]` writes
`summaries/summarize.prompt.md` (a prompt for the agent, not a finished
summary) and classifies every source rather than re-soliciting all of them. Each
`summaries/sources/<name>.md` carries a `source_rev` frontmatter line
(`SUMMARY_REV_KEY`) pinning it to the locked identity it was generated from. On each
run the command builds `_locked_source_index()` — repos/papers/notes from
`lock["sources"]`, docs from the top-level `lock["doc_snapshots"]` — and
`_locked_source_rev()` returns the comparable identity (repo `head`/`commit`, or a
doc's `content_hash` only when `status == "ok"`). The per-source cascade:

1. `--force` → **todo** (regenerate).
2. A doc snapshot whose status is `flagged` → **review** (never summarized from
   quarantined content).
3. No summary file → **todo** (`new`).
4. Summary has `source_rev`: differs from the locked rev → **todo** (`changed`);
   matches → **keep**.
5. Legacy summary with no `source_rev` → a timestamp fallback
   (`_source_changed_at` vs `_summary_written_at`): for repos this keys on the HEAD
   commit's committer date (`_git_commit_date`), which moves only on real change —
   not `fetched_at`, which a re-fetch can bump; docs/papers/notes fall back to
   `fetched_at`. Stale only if the source changed after the summary was written;
   otherwise **keep** (annotated "unverified"). The fallback is self-retiring —
   any refresh stamps a real `source_rev`.

The emitted prompt opens with a **Workspace focus** block (`_summarize_focus_lines`:
the atlas `name`+`description`, the current effort's `description` when it is not the
default `main` blurb, and a `--focus` override), then lists "Summarize these (new or
changed)" with the exact `source_rev` to stamp, "Keep as-is," "Review needed"
(flagged docs), and orphaned summaries (noted, never auto-deleted). `--focus` is
per-run only and does not mutate the atlas.

### Dependency posture and `docs/snapshots/` layout

Runtime carries two core dependencies (`pyproject.toml`): `graphifyy` for the
knowledge graph and `trafilatura` for HTML main-content extraction, both bundled so a
plain install can build a graph and snapshot a doc site. `[docs-scan]` (LLM Guard) is
the only extra that adds packages; `[graph]` remains as an empty compatibility alias
for installs that named it before the runtime was bundled.
Snapshots are single files under `docs/snapshots/`; flagged files
(`*.flagged.*`) are gitignored by the generated workspace `.gitignore`.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Docs schema | Reuse the `docs` kind + optional `kind` field; never a new `api/` kind | Avoids a parallel top-level concept for what is still "upstream-authored reference material." |
| External vs in-repo source | One of `url` *or* (`repo`+`path`), validated mutually exclusive | In-repo specs are already local after `fetch`; only external sites need network snapshotting. |
| Snapshotting command | Separate `fetch-docs`, not folded into `fetch` | Crawling arbitrary sites has a different risk/latency profile than cloning pinned git repos; keeps `fetch` fast and predictable. |
| External fetch | `llms.txt` → Trafilatura single-page Markdown → stdlib fallback → reference-only | Prefers a site's own LLM-ready file, otherwise removes navigation/sidebars while retaining a deterministic no-crash fallback. |
| Fetch failure | Never fail the entry; record `reference-only` with `no-source` (quiet) vs `fetch-error` (loud) | A doc reference is still useful as a live pointer; a real failure must be diagnosable. |
| Safety pass placement | At fetch time, before anything is written | A snapshot is committed and re-read forever; sanitize closest to the source, fewest code paths a payload survives. |
| Flagged content | Quarantine + human-in-the-loop; never auto-trust or silently strip | Injection detection is undecidable; architectural controls fail safe where model-level mitigations can be steered by the injected text. |
| Deep scanner | Opt-in `[docs-scan]`, layered on top of the mandatory stdlib baseline, fail-safe load | Heavy ML deps enlarge Zentaizo's own attack surface; the baseline must always run and never crash. |
| Summary provenance | Pin each summary to `source_rev`, diff against the lock | The lock already records resolved identity; a summary need only claim the one state it describes. |
| Legacy summaries | Timestamp fallback (repo commit date, else `fetched_at`), self-retiring | Adopting incrementality must not force a one-time full regenerate of existing work. |
| Generated API docs | Live in `summaries/`, not synthetic `docs/` entries | Keeps the invariant that `docs/` is upstream-authored and `summaries/` is workspace-generated. |

## Decision update — 2026-07-24

Trafilatura 2.x moved from the deferred `[docs]` tier into the default
installation. The shipped `main-content-v1` profile uses Markdown output,
tables on, comments and links off, and the balanced extraction mode. It records
the exact extractor version because output is repeatable for a fixed version,
not guaranteed identical across heuristic releases. The heavier crawling and
multi-file `[docs-rich]` direction remains deferred.

## Considered and not taken

- **CLI-side OpenAPI/Swagger → Markdown conversion** — skipped; raw spec + AI
  summarize is enough, and OpenAPI YAML is already LLM-legible.
- **Heavy crawlers and full-site mirroring** — the `[docs-rich]`
  (Crawl4AI/Firecrawl, Read-the-Docs archive extraction, `wget` mirror) tier and
  the directory/multi-file snapshot model it implies remain deferred; the
  shipped path stays single-page and deterministic.
- **A new top-level `api/` source kind** — rejected in favor of reusing `docs` with
  a `kind` field.
- **Folding doc snapshotting into `fetch`** — rejected; doc fetching stays an
  explicit, opt-in subcommand.
- **Auto-deleting orphaned summaries / atlas mutation by `summarize`** — out of
  scope; orphans are noted only, and `--focus` never writes to the atlas. A
  `summaries.focus` atlas field and `zentaizo status` summary-coverage reporting
  remain follow-ons.

## See also

- `docs/cli.md` — command reference for `discover-docs`, `fetch-docs`, `summarize`.
- `docs/workspace-format.md` — the atlas `docs` schema, `kind`/source discriminator,
  the lock, and the summaries hierarchy.
- `README.md` — the level-of-detail spine and the untrusted-input posture.
- `src/zentaizo/cli.py` — `validate_doc_entries`, `discover_docs_workspace`,
  `fetch_docs_workspace`, `_fetch_external_doc`, `_apply_safety_and_write`,
  `summarize_workspace` and its staleness helpers.
- `src/zentaizo/extract.py` — the versioned Trafilatura profile and guarded
  fallback boundary.
- `src/zentaizo/safety.py`, `src/zentaizo/_llm_guard_scan.py` — the fetch-time safety
  pass and the optional `[docs-scan]` deep scanner.
