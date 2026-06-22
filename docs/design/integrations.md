# External Knowledge Integrations

_Distilled design doc — current architecture + rationale._

## What it is

Zentaizo keeps its core CLI thin and deterministic, but a workspace can gain
extra capability from external tools wired in as **optional tiers**. Each tier
follows one standing rule: prefer the best backend that is installed, never make
it a hard dependency, and fail safe (reference-only, or a clear install hint)
when the tool is absent. The integration surface is deliberately small — the CLI
owns workspace conventions (what to include, where output lives, how provenance
and staleness are tracked) and delegates the heavy lifting to the external tool.

Today the integration layer has one shipped member: a workspace knowledge-graph
layer (`zentaizo graph`) built over [Graphify](https://github.com/safishamsi/graphify).
A second direction — sourcing API reference docs through Context Hub — is an open
proposal and is not implemented. The two are described separately below so the
built-vs-proposed split is unambiguous.

## Architecture

### Graphify graph layer — `zentaizo graph` (built)

`zentaizo graph` derives a single queryable knowledge graph over the whole
workspace. It is the structural counterpart to `summaries/`: where summaries are
the prose level-of-detail spine, the graph answers structural questions
(`graphify query` / `path` / `explain`, or Graphify's MCP server) — especially
the cross-repo and code↔doc edges no per-repo run can see. It is not a fetcher;
it derives structure from what `fetch`/`fetch-docs` already snapshotted, so it
sits as a sibling of `summarize`, not inside the fetch cascade.

The verb is capability-named with Graphify as the first backend tier. Graphify
owns installation, per-assistant skill registration, the build engine and its
semantic backends, and the entire query surface — none of which Zentaizo wraps.
Zentaizo owns only the workspace conventions Graphify cannot know: what to graph
and in which mode, where output lives, provenance/staleness, and the one
consultation-order line in the generated `AGENTS.md`.

How it works in current code (`graph_workspace` and helpers in
`src/zentaizo/cli.py`):

- **PATH gate, never auto-install.** `shutil.which("graphify")` must succeed; a
  missing binary exits nonzero with the exact install commands
  (`uv tool install graphifyy`, or `pip install "zentaizo[graph]"`). The
  optional `graph` extra (`graphifyy>=0.8.39`) exists for a pinned in-environment
  install, but the runtime gate is the binary on PATH, not the extra. Installing
  is the user's call: the right installer and target are environment-specific,
  and an implicit network install would mutate state outside the workspace
  boundary — out of character for a thin, fail-safe CLI.
- **Two execution modes, because extraction is not uniformly offline.** Default
  is code-only and fully offline: `graphify update .` runs AST extraction (plus
  shallow markdown structure) with no key and no network. `--semantic` opts into
  full-corpus extraction of papers and notes through a model API and **requires
  an explicit `--backend`** (`--semantic` without `--backend` is an error) so
  that where workspace content is sent is stated intent, not whichever API key
  happens to be set; the resolved backend/model is recorded in the lock.
- **Deterministic input set via a managed `.graphifyignore`.** The command
  computes which source trees to graph from the workspace layout (`repos/`,
  `papers/`, `notes/`; doc snapshots are excluded — see below) and writes a
  marker-tagged, regenerated `.graphifyignore` at the workspace root. Graphify
  reads this *instead of* the workspace `.gitignore` in the same directory, which
  is precisely what makes the gitignored `repos/` graphable while keeping the
  process trail (`sessions/`, `summaries/`, `skills/`, `tmp/`, atlas+lock,
  flagged snapshots) out. A user-owned `.graphifyignore` without the marker is
  refused, never overwritten.
- **Output and commit policy.** Graphify runs with CWD = workspace root scanning
  `.` (which coalesces all output into one `graphify-out/`), under
  `PYTHONHASHSEED=0` (reproducible clustering) and `GRAPHIFY_NO_BACKUP=1` (git
  history is the backup). `graphify-out/` is committed — `graph.json` is
  machine-derived state like the lock, `GRAPH_REPORT.md` is markdown context like
  a summary — except `cost.json` and `cache/stat-index.json`, which are
  gitignored.
- **The report goes through the docs-scan safety pass.** `GRAPH_REPORT.md` is
  extraction *from* untrusted sources and is the one artifact agents read as
  prose, so it runs the same sanitize/flag pass as fetched docs with mechanical
  move-aside quarantine: a flagged verdict moves it to `GRAPH_REPORT.flagged.md`
  and leaves nothing in place — absence *is* the quarantine — recording
  `report_status: flagged` plus the quarantine path in the lock.
- **Provenance and staleness in the lock.** A successful build writes a top-level
  `graph` block: backend and version, `mode`, `built_from` (each graphed source
  mapped to its locked identity), `not_graphed` (excluded sources mapped to
  reasons), and `report_status`. `built_from` is **mode-scoped** — only what
  Graphify actually read in that mode — so a doc-snapshot hash change never
  stales a code-only graph. Staleness is a pure lock diff scoped to the recorded
  mode; `zentaizo status` reports `not built` / `current` / `stale`. Papers and
  notes have no locked content identity, so they are recorded as unfetched and
  delegate change detection to Graphify's own SHA256 cache during `--update`.
- **Fetch keeps the graph fresh, code-only.** When the lock carries a `graph`
  block and a graphed source's rev changed, `zentaizo fetch` best-effort refreshes
  the graph in code-only mode (AST, offline) — never failing the fetch.
  `--no-graph` opts out; semantic re-extraction always stays an explicit command.

One known upstream limit (graphifyy 0.8.39): any directory named `snapshots` is
on Graphify's built-in skip list, so `docs/snapshots/` cannot be graphed in
either mode and is always listed under `not_graphed`.

### Proposed: Context Hub (`chub`) — not implemented

There is **no Context Hub or `chub` code in the repo**; this is an open
direction, not a shipped feature. The idea: expose
[Context Hub](https://github.com/andrewyng/context-hub) — a registry of curated,
versioned, language-specific API reference docs — as an optional fetcher tier
(`zentaizo[docs-chub]`) so a workspace could pull a registry doc into
`docs/snapshots/` through the same safety pass and lock machinery as any other
doc source.

The sketch follows the same integration philosophy: a marker extra plus a
"is `chub` on PATH" gate (it is an npm package, so it cannot ride
`pip install`), a third mutually-exclusive `docs` source discriminator (`chub`
id with optional `lang`/`version` selectors), and no inheritance of chub's "the
registry is curated, therefore trusted" assumption — registry content would be
sanitized/quarantined like any other untrusted external markdown.

**Open follow-up before adoption:** the Context Hub direction should be
contrasted with [Context7](https://context7.com) (a competing
current-API-docs-for-agents service) and compared against the Graphify graph
layer — chub is a fetcher that *brings docs in*, while the graph layer *derives
structure* from what is already snapshotted. Whether chub earns its own tier, or
whether the graph layer (or an existing doc fetcher) already covers the need, is
an open question, not a decision.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Integration shape | Optional tier, never a hard dependency; fail safe when absent | Keeps the core CLI thin and deterministic; a workspace works without any external tool |
| `zentaizo graph` install | PATH gate only; never auto-install (exit with exact commands) | Installer/target are environment-specific; implicit network installs mutate state outside the workspace |
| Graph placement | Sibling of `summarize` (derived layer), not a fetcher | The graph derives structure from snapshotted sources; it brings nothing in |
| Graph scope | One graph over the whole workspace | Cross-source (cross-repo, code↔doc) edges are the value a per-repo run can't see |
| Execution modes | Code-only/offline default; `--semantic` opt-in, explicit `--backend` required | Only code extraction is local AST; semantic extraction is a model-API/cost/data-residency event that must be stated intent |
| `GRAPH_REPORT.md` | Same docs-scan safety pass; move-aside quarantine | It is prose agents read, extracted from untrusted sources |
| Output | Commit `graphify-out/` (minus `cost.json`, `cache/stat-index.json`) | `graph.json` is machine state like the lock; a fresh clone gets the map and `--update` diffs against it |
| Provenance | Mode-scoped `built_from` + `not_graphed` in the lock | A source the mode never read must not stale the graph |
| Fetch refresh | Best-effort, code-only, never fails the fetch | A code-only refresh is local/deterministic; an implicit semantic refresh would not be |
| Context Hub | Proposed only — not implemented | Open direction pending a Context7/graph-layer comparison |

## Considered and not taken

- **Wrapping Graphify's query surface** (`query`/`path`/`explain`/MCP) — left
  Graphify-native; Zentaizo only points agents at it.
- **A per-source `graph: false` atlas opt-out** — not added until a real
  workspace needs it (explicit boring JSON, but not preemptive JSON).
- **Auto-installing the graph backend, or registering its skill** — both are
  user-level concerns; the workspace only needs the binary.
- **Graphing the `sessions/` process trail, or Graphify's cross-project
  `--global` graph** — out of scope; single-workspace graphing of the *system*
  only.
- **Treating Context Hub registry content as pre-trusted** — would not be
  adopted even if chub ships; curation reduces, not eliminates, prompt-injection
  risk.

## See also

- `src/zentaizo/cli.py` — `graph_workspace` and the `_graph_*` / `_run_graphify`
  / `_scan_graph_report` helpers; the `--no-graph` fetch refresh.
- `docs/cli.md` — the `zentaizo graph` and `zentaizo fetch --no-graph` command
  reference.
- `docs/workspace-format.md` — the `graphify-out/` layout, the lock `graph`
  block, and the Graph section beside Summaries.
- `README.md` — "Querying a knowledge graph" and the optional-layers framing.
