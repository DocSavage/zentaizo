---
created: 2026-06-12
status: proposed
edited_by:
  - 2026-06-12  Claude Fable 5
  - 2026-06-12  Codex (review)
  - 2026-06-12  Claude Fable 5
  - 2026-06-12  Codex (review, 2nd pass)
  - 2026-06-12  Claude Fable 5
  - 2026-06-12  Codex (review, 3rd pass)
  - 2026-06-12  Claude Fable 5
  - 2026-06-12  Claude Fable 5 (step-1 verification against graphifyy 0.8.39)
---

# Graphify as a workspace knowledge-graph layer (`zentaizo graph`)

_Design doc. Drafted 2026-06-12. Proposes integrating
[Graphify](https://github.com/safishamsi/graphify) — the open-source
knowledge-graph skill for AI coding assistants — as an optional derived-context
layer in a Zentaizo workspace, built by a new `zentaizo graph` verb and
surfaced to agents through one line in the generated `AGENTS.md` consultation
order. Follows the external-tool integration pattern set by
`2026-05-26-context-hub-integration-plan.md`: **optional tier, never a hard
dependency, fail safe when absent** — but lands at a different stage of the
pipeline (a sibling of `summarize`, not a fetcher inside `fetch-docs`)._

_Revised 2026-06-12 after review: the three open questions are decided —
`graph.json` **is committed** (upstream's own model), `GRAPH_REPORT.md` goes
through the docs-scan safety pass, and `fetch` keeps the graph fresh itself
(best-effort auto-refresh; the stale hint is only the fallback). The output
directory is upstream-fixed `graphify-out/`, not a Zentaizo-chosen `graph/`._

_Revised again 2026-06-12 after a Codex review (findings verified against the
raw upstream README and this repo's code): the "zero API calls" premise was
wrong — only code extraction is local AST; docs/PDFs/images go through a
model API. The design now splits execution modes (**code-only/offline by
default, `--semantic` opt-in**), generates a **managed `.graphifyignore`**
(the workspace `.gitignore` would otherwise hide `repos/` from Graphify),
reuses summarize's `unfetched` class for papers/notes provenance, gives a
flagged `GRAPH_REPORT.md` real move-aside quarantine mechanics, and restates
the commit policy as a Zentaizo choice on top of upstream's recommendation
rather than "exactly upstream's split". Fetch auto-refresh survives, narrowed
to code-only — the line upstream's own post-commit hook draws ("AST only, no
API cost")._

_Amended 2026-06-12 (same session): the workspace `.gitignore` stops ignoring
`docs/snapshots/` and `papers/*.pdf` — that content is committed from now on
(papers have no fetcher and were unrecoverable from a clone). The managed
`.graphifyignore` remains necessary regardless: `repos/` stays gitignored but
must be graphed, and the committed process trail must not be._

_Second Codex pass 2026-06-12: direction signed off; two should-fixes folded
in — `fetch` auto-refresh of a `mode: semantic` graph is gated on build step 1
proving an AST-only `--update` preserves semantic nodes, and the
commit-`cache/` default is gated on a step-1 inspection of cache contents
(raw `repos/` source chunks in the cache would flip it). Plus a verified nit:
Graphify logs every query to `~/.cache/graphify-queries.log` by default; the
consultation bullet gains the opt-out for sensitive workspaces._

_Third Codex pass 2026-06-12: provenance is now mode-scoped — `built_from`
records only what Graphify actually read, with semantic-only sources in a
`not_graphed` list, so a doc hash change cannot stale a code-only graph;
`--semantic` now requires an explicit `--backend` (recorded in the lock)
instead of riding key auto-detection; the sandbox build-order step gains the
managed `.graphifyignore`; and the plan carries a named test plan._

_Step-1 verification 2026-06-12, against **graphifyy 0.8.39** (installed via
pipx; version floor for the extra). All five gated questions answered — see
**Step-1 findings** below. Both provisional defaults resolved: `cache/` is
**committed** (entries hold extracted nodes/edges only, no raw source chunks;
`cache/stat-index.json` is the one exception — machine-local stat memo,
gitignored), and fetch auto-refresh **extends to `mode: semantic` graphs**
(an AST-only `graphify update` provably preserves semantic nodes and edges).
Two findings the plan did not anticipate: per directory, `.graphifyignore`
**replaces** `.gitignore` rather than overlaying it, so the managed file must
carry the workspace's full graph-exclusion set itself (and needs no `!repos/`
negation at all); and Graphify hard-skips any directory named `snapshots`
(a Jest/Vitest convention baked into its `_SKIP_DIRS`), which makes
`docs/snapshots/` **ungraphable in 0.8.39 in either mode** — doc snapshots
are recorded under `not_graphed` with an explicit reason until upstream
offers an escape hatch._

## Context — what Graphify is

Graphify ([repo](https://github.com/safishamsi/graphify),
[site](https://graphify.net/)) is a Python CLI (PyPI package `graphifyy`,
command `graphify`) that builds a queryable knowledge graph from a folder of
code, SQL, docs, PDFs, and images. The extraction model is **split, and the
split matters for everything below**: code is extracted locally via
tree-sitter AST with no API calls, but everything else — markdown docs, PDFs,
images, video — goes through a model API for semantic extraction. In skill
mode (`/graphify`) that is the IDE session's own model; headless
`graphify extract` needs an explicit backend (`--backend ollama` is fully
local, `--backend claude-cli` uses a Claude subscription with no key, and
gemini/openai/deepseek/kimi/bedrock/azure are remote). A code-only corpus
runs fully offline with no key. As of mid-2026 it is widely adopted (tens of
thousands of GitHub stars, 1M+ PyPI downloads; YC S26).

```bash
uv tool install graphifyy     # or pipx / pip
graphify install              # register the skill with installed assistants
```

`graphify install` registers a `/graphify` skill across Claude Code, Codex,
Cursor, Gemini CLI, Aider, and others — agent recognition of the *tool* is
Graphify's own job and already solved; this plan does not duplicate it.

Running `graphify` (or `/graphify .` from inside an assistant) over a tree
emits a `graphify-out/` directory:

- `graph.json` — the complete queryable graph (nodes, edges, confidence tags
  `EXTRACTED` / `INFERRED` / `AMBIGUOUS`)
- `GRAPH_REPORT.md` — key concepts, most-connected "god nodes", surprising
  cross-module links, suggested questions
- `graph.html` — interactive visualization
- `manifest.json` — portable (relative paths, re-anchored on load);
  upstream says committing it is safe and avoids a full rebuild on first
  checkout
- `cache/` — SHA256-keyed extraction cache; re-runs only process changed files
- `cost.json` — local-only run costs (upstream's one recommended `.gitignore`
  entry)
- optional `obsidian/`, `wiki/`, `converted/` subtrees

Graph state is **directory-local** — there is no implicit user-level cache
(an opt-in cross-project "global graph" exists; out of scope here).
Upstream's docs say `graphify-out/` "is meant to be committed to git so
everyone on the team starts with a map"; `--update` re-extracts only changed
files (detected via the SHA256 `cache/`), diffing against the existing
committed graph. Upstream even ships `graphify hook install` — a post-commit
auto-rebuild that is explicitly "AST only, no API cost" — plus a git merge
driver so a committed `graph.json` union-merges across parallel commits. The
build's output location is not configurable (only `graphify export …
--output` takes a path), so the directory name `graphify-out/` is fixed. The
headless build verb is `graphify extract <path>`; `/graphify` is its skill
form.

Querying is Graphify-native and stays that way:

```bash
graphify query "what connects auth to database?"
graphify path "UserService" "DatabasePool"
graphify explain "RateLimiter"
python -m graphify.serve graphify-out/graph.json   # MCP server
```

When files change, `graphify <path> --update` re-extracts only the affected
subgraph and patches the live graph incrementally (sub-second on small change
sets, per its docs), so "re-run after fetch" is cheap. Graphify's own
`--force` overwrites `graph.json` even when the new graph has fewer nodes.

## Why this maps onto a workspace

A Zentaizo workspace is exactly Graphify's multi-modal sweet spot: multiple
repo snapshots plus doc snapshots plus papers plus notes in one tree. A single
graph built over the whole workspace surfaces **cross-repo and code↔doc↔paper
edges that no per-repo `/graphify .` run inside any single repo can see** —
that cross-source connectivity is the workspace's reason to exist, and it is
the value-add that justifies a tier rather than a README mention.

Where it sits in the existing model:

- It is **not a fetcher** (the chub integration's slot): it brings nothing into
  the workspace; it derives structure from what `fetch` / `fetch-docs` already
  snapshotted.
- It **is a derived-context layer**, a sibling of `summaries/`: the summaries
  are the prose level-of-detail spine; the graph is the structural counterpart
  (queryable relationships instead of narrative). `GRAPH_REPORT.md` is
  committed markdown context like a summary; `graph.json` is machine-derived
  state like the lock.
- The atlas/lock contract extends cleanly: the atlas stays human intent, the
  lock records what resolved state the graph was built from, and staleness is
  a diff against the lock — the same provenance shape `summarize` adopted in
  `2026-06-08-incremental-summarize.md`.

## Division of labor

**Graphify owns:** installation, per-assistant skill registration
(`graphify install`), the build engine (including the semantic-extraction
backends and their credentials), and the entire query surface
(`query` / `path` / `explain` / MCP). None of that is wrapped.

**Zentaizo owns** the workspace conventions Graphify cannot know:

1. *What to graph, and in which mode* — which parts of the workspace are
   system sources and which are process trail (sessions/, derived summaries)
   that would pollute the graph; and whether a build is offline code-only or
   opt-in semantic extraction that calls a model API (§2).
2. *Where the output lives* in the workspace layout.
3. *Provenance and staleness* — which locked source revisions the graph was
   built from, and reporting drift after a `fetch`.
4. *Discovery within the workspace* — the one consultation-order line in the
   generated `AGENTS.md` that tells a session the graph exists and how to ask
   it questions.

## Design

### 1. Verb naming: `zentaizo graph`, with Graphify as the first backend

Capability-named verb, backend as a tier — the same pattern the chub plan used
(`zentaizo[docs-chub]` behind the generic docs cascade) and the standing
"prefer the best backend that is installed, fail safe" philosophy. The verb
stays stable if a different graph backend ever matters; today Graphify is the
only tier.

Unlike chub (npm), `graphifyy` is pip-installable, so a real extra is possible:

```toml
[project.optional-dependencies]
graph = ["graphifyy>=0.8.39"]   # floor = the version step 1 verified
```

The **runtime gate is still "is `graphify` on PATH"**, not "is the extra
installed" — most users will have it as a `uv tool` / `pipx` install outside
Zentaizo's environment (it is an assistant-level tool, not a workspace-level
one). If the binary is absent, `zentaizo graph` exits with the install
one-liner and a nonzero status; nothing else in the workspace depends on it.

**Why `zentaizo graph` does not install Graphify itself.** Deliberate, for the
same reasons the chub plan made its gate "is the binary on PATH":

- *Environment ambiguity.* The right installer is the user's call — `uv tool`,
  `pipx`, conda, system pip — and each puts the binary somewhere different.
  Guessing wrong leaves a `graphify` that Zentaizo's environment can see but
  the user's shell (or another assistant harness shelling out to it) cannot.
- *Side-effect scope.* Everything Zentaizo installs today (skills, hooks) is a
  bundled file copied into the workspace. A PyPI install triggered implicitly
  on first use is a network side effect that mutates the user's environment
  outside the workspace boundary — out of character for a thin, deterministic,
  fail-safe CLI.

So the failure mode prints the exact commands — `uv tool install graphifyy`,
or `pip install "zentaizo[graph]"` to carry a pinned-compatible Graphify
inside Zentaizo's own environment — and exits nonzero. (`uv tool`/`pipx`
stay the primary recommendation: upstream cautions against bare `pip` on
macOS/Windows because the *skill* resolves its Python from
`graphify-out/.graphify_python`; the extra is fine for `zentaizo graph`'s
direct binary invocation.) Note that
`graphify install` (per-assistant skill registration) is *not* required for
workspace use: inside a workspace the generated `AGENTS.md` gives the agent
the query commands directly, so only the binary matters here.

### 2. Execution modes and the input set

**Two modes, because extraction is not uniformly offline** (Codex review
finding 1). Code extraction is local AST; markdown docs, PDFs, and images
require a model API call. Conflating the two would make "rebuild the graph" a
network/cost/data-residency event, which poisons both the fetch auto-refresh
(§4) and the sandbox story (§6):

- **`zentaizo graph` (default) — code-only, fully offline.** AST extraction
  over the source trees: no key, no network. This is the only mode `fetch`
  may auto-refresh and the mode that is sandbox-clean — the same line
  upstream's own post-commit hook draws ("auto-rebuild after each commit —
  AST only, no API cost"). Mechanism (pinned by step 1): **`graphify update
  .`** — the CLI verb backed by the same `_rebuild_code()` engine the hook
  launches. Note it is "offline", not strictly "code-files-only": markdown
  gets shallow structural extraction (file + headings, zero tokens) on the
  same pass.
- **`zentaizo graph --semantic` — opt-in full-corpus extraction.** Adds
  docs/papers/notes content via LLM extraction. Requires an **explicit
  backend**: `--semantic` without `--backend` is an error that lists the
  options (third Codex pass — Graphify's own auto-detection silently picks a
  provider by whichever API key happens to be set, and where workspace
  content gets sent must be stated intent, not ambient environment).
  `--backend` (and `--model`) pass through verbatim — `ollama` is fully
  local, `claude-cli` needs no key, and remote backends with their
  data-residency implications (e.g. Kimi routes to Moonshot servers in
  China) are the user's explicit call; the resolved choice is recorded in
  the lock (`semantic_backend` / `semantic_model`, §4). Re-runs are
  incremental:
  Graphify's SHA256 `cache/` means unchanged files are never re-extracted,
  so a refresh only pays for what changed.

**The input set** is computed deterministically from the workspace layout —
the main reason a CLI verb beats a documented convention (the "CLI is
deterministic; the assistant exercises judgment" principle from the summarize
design; without the verb every agent re-derives the include/exclude list and
nothing records provenance):

- **Included:** `repos/`, `docs/`, `papers/`, `notes/` — the four primary
  source trees (in full under `--semantic`; the default mode reaches code
  plus shallow markdown structure). Caveat from step 1: under graphifyy
  0.8.39, `docs/snapshots/` is pruned by the tool's built-in skip list in
  either mode and lands in `not_graphed` (findings, item 4).
- **Excluded:** `sessions/` (workspace process trail, not the system),
  `summaries/` (derived prose; graphing a derivative alongside its sources
  creates edges between text *about* the system and the system), `skills/`,
  `tmp/`, `graphify-out/` itself, and `.git` internals.

**The mechanics: a workspace-`.gitignore` change plus a managed ignore file**
(Codex review finding 2). Graphify respects per-directory `.gitignore`
automatically — and the generated workspace `.gitignore` (`cli.py:798`) hides
`repos/`, `docs/snapshots/`, and `papers/*.pdf` from it, so a naive
workspace-root run would skip precisely the source material while graphing
the process files. Two-part resolution, the first part decided 2026-06-12:

- **The workspace `.gitignore` stops ignoring `docs/snapshots/` and
  `papers/*.pdf` — that content is committed.** This is a workspace policy
  change in its own right, not just a graphing fix: papers are hand-placed
  (`fetch` only records them in the lock and defers snapshotting,
  `cli.py:1396` — there is no paper fetcher), so a gitignored `papers/` was
  simply unrecoverable from a clone; and a committed doc snapshot pins the
  exact sanitized text that the safety pass reviewed and that the
  `content_hash` in the lock, summaries, and graph `built_from` refers to.
  It also repairs an odd posture: committing `graphify-out/` (the
  derivative) while gitignoring its sources. Quarantined files stay out —
  `docs/snapshots/*.flagged.*` is added to the template, so flagged content
  is never committed and pulled onto another machine.
- **`repos/` stays gitignored — and must still be graphed.** That conflict
  cannot be resolved in `.gitignore` (fetched repos do not belong in the
  workspace's git), so `zentaizo graph` writes a **managed `.graphifyignore`
  at the workspace root** (marker comment, regenerated per build — the
  commit-attribution-hook pattern). `.graphifyignore` is Graphify's own
  ignore format — same syntax as `.gitignore` including `!` negation —
  but step 1 corrected the plan's model of how it combines: per directory it
  **replaces** that directory's `.gitignore` (the fallback reads
  `.gitignore` only when no `.graphifyignore` exists), and only the scan
  root's (and its ancestors') ignore files are loaded — nested ignore files
  inside subtrees are never read. So the managed file needs no `!repos/`
  negation (with it present, the root `.gitignore` is simply not consulted
  and `repos/` is visible), and it must instead carry the workspace's full
  graph-exclusion set itself: `sessions/`, `summaries/`, `skills/`, `tmp/`,
  the atlas and lock, and `docs/snapshots/*.flagged.*`. A fetched repo's own
  `.gitignore` does **not** apply inside `repos/`; artifact hygiene there
  rests on Graphify's built-in skip list (node_modules, dist, build, target,
  venvs, framework caches, …), which covers the heavy cases. The managed
  file is deterministic output, committed like the lock. One upstream
  collision discovered here: that built-in skip list hard-prunes any
  directory named `snapshots`, so **`docs/snapshots/` is ungraphable in
  0.8.39 in either mode** — doc snapshots land in `not_graphed` with an
  explicit reason (see Step-1 findings, item 4).

One graph for the whole workspace, not per-source subgraphs — the cross-source
edges are the point (§ Why this maps). A per-source opt-out knob in the atlas
(e.g. `graph: false` on a huge reference repo) is deliberately **not** added
until a real workspace needs it: explicit boring JSON, but not preemptive
JSON.

### 3. Output location and commit policy

The workspace adopts **`graphify-out/` at the workspace root** — step 1
found the location *is* configurable in 0.8.39 (`extract --out`,
`GRAPHIFY_OUT` env var), but there is no reason to diverge from upstream's
default. `zentaizo graph` runs the binary with CWD = workspace root scanning
`.`: step 1 caught a 0.8.39 quirk where `manifest.json` is written to
`$CWD/graphify-out/` while everything else goes to the scanned path's
`graphify-out/`, and CWD = scanned path is what coalesces them. The lock
records the observed `output_dir`:

```text
graphify-out/
  graph.json              # committed — machine-derived, like the lock
  GRAPH_REPORT.md         # committed — markdown context, like a summary
  graph.html              # committed — regenerable, but upstream ships it as part of the map
  manifest.json           # committed — portable; avoids a full rebuild on first checkout
  cache/                  # committed (finalized by step 1: entries hold extracted
                          #   nodes/edges only, no raw source chunks)
  cache/stat-index.json   # gitignored — machine-local stat memo (absolute paths, mtimes)
  cost.json               # gitignored — local-only
```

Commit policy (decided 2026-06-12; phrasing corrected after the Codex review —
this is a **Zentaizo policy choice built on upstream's recommendation**, not
a verbatim copy of it): commit `graphify-out/`, gitignore only `cost.json`.
Upstream's own split is: commit the directory ("meant to be committed to git
so everyone on the team starts with a map"), ignore `cost.json` (local only),
`cache/` optional ("commit for speed, skip to keep repo small"),
`manifest.json` safe and worth committing. Zentaizo **commits `cache/`** —
the provisional default, finalized by the step-1 inspection: AST entries
(`cache/ast/v<version>/`, version-namespaced) and semantic entries
(`cache/semantic/`) both contain extracted nodes/edges only, **no raw source
chunks** (verified in source and empirically), so committing the cache leaks
nothing beyond what the committed `graph.json` already carries. The cache is
what spares a fresh clone from re-paying model-API extraction for unchanged
sources — `repos/` are re-fetched rather than carried in git, and with doc
snapshots and papers now committed (§2) the cache keyed to that content
naturally travels with it. One carve-out from the same inspection:
`cache/stat-index.json` is a rebuildable stat memo holding absolute paths
and nanosecond mtimes — pure machine-local churn — and is gitignored. Two
invocation details also land here (step-1 findings 2 and 8): `zentaizo
graph` runs Graphify with `PYTHONHASHSEED=0` (deterministic community
clustering, so the committed `graph.json` is reproducible) and
`GRAPHIFY_NO_BACKUP=1` (Graphify otherwise snapshots semantic graphs to
dated `graphify-out/<YYYY-MM-DD>/` dirs before overwrite; in a workspace,
git history is that backup). Committing `graph.json` is what makes the layer
workspace-local in the Zentaizo sense: a fresh clone has the graph
immediately, `--update` diffs against the committed state instead of
rebuilding from scratch (upstream's merge driver keeps parallel commits
union-merged), and the graph travels with the lock that vouches for it. The
workspace `.gitignore` template gains `graphify-out/cost.json` and
`graphify-out/cache/stat-index.json` here; the snapshot/papers un-ignoring
lives in §2.

**`GRAPH_REPORT.md` goes through the same docs-scan safety pass** that
`fetch-docs` applies (decided 2026-06-12; no exception for locally-generated
content — it is extraction *from* untrusted sources, and it is the one
artifact agents read as prose). Per the Codex review, the quarantine is
mechanical, not advisory, mirroring `_write_snapshot_or_quarantine`
(`cli.py:1439`): on a flagged verdict the report is **moved to
`GRAPH_REPORT.flagged.md`** — no `GRAPH_REPORT.md` is left in place, so
absence *is* the quarantine, exactly as a flagged doc snapshot is "written to
a `.flagged` path and never surfaced" — and the lock `graph` block records
`report_status: flagged` plus the quarantine path. `zentaizo status` surfaces
it; the consultation bullet only ever points at a `GRAPH_REPORT.md` that
exists. (`graph.json` is structured data agents reach through Graphify's
query tools, not prose they read; the standing untrusted-input rule covers
it.)

### 4. Lock provenance and staleness

`zentaizo graph` records a top-level `graph` block in `zentaizo.lock.json`
after a successful build:

```json
"graph": {
  "backend": "graphify",
  "backend_version": "1.4.2",
  "mode": "code-only",
  "built_at": "2026-06-12T15:04:11Z",
  "output_dir": "graphify-out",
  "report_status": "ok",
  "built_from": {
    "repos/shortener-api": "9f3a1c4e7b…",
    "repos/deployment": "2c61d0aa00…",
    "notes": "unfetched"
  },
  "not_graphed": {
    "docs/api-docs": "skipped by graphify (snapshots dir)",
    "papers/whitepaper": "semantic-only source (code-only build)"
  }
}
```

(`not_graphed` maps each excluded source to the reason, so `status` can say
why. Notes appear in `built_from` in **both** modes — step 1 found that the
AST-only path performs shallow markdown extraction (file + heading nodes,
offline), so notes are genuinely read even code-only; as `"unfetched"`
sources they never drive staleness. A `--semantic` build adds
`"semantic_backend"` / `"semantic_model"` and moves papers into `built_from`
as `"unfetched"`. Doc snapshots stay in `not_graphed` in both modes under
graphifyy 0.8.39 — its built-in skip list prunes any `snapshots` directory
(Step-1 findings, item 4).)

`built_from` maps **each source actually handed to Graphify for the recorded
`mode`** — only those (third Codex pass) — to the same locked identity
`summarize` pins (`repo` commit/head; doc snapshot `content_hash`): the lock
stays the single source-state oracle, no second record is invented. Sources
the mode excludes (markdown docs, PDFs, notes under `code-only`) go in the
sibling `not_graphed` list instead — a doc snapshot's `content_hash` moving
must never stale a code-only graph that never read it. Papers
and notes have **no locked content identity** today (Codex review finding 3),
and `summarize` already names this class: its `UNFETCHED_REV` placeholder
covers "papers, notes, un-snapshotted/reference-only docs" (`cli.py:1810`).
The graph reuses it verbatim — when such sources are graphed (i.e. under
`--semantic`), they are recorded as `"unfetched"` in `built_from`, never
drive rev-diff staleness, and are listed by `status` as untracked. Their actual change detection is delegated to Graphify's own
SHA256 `cache/` during `--update`, which re-extracts exactly the files whose
content changed — so nothing goes silently stale; it is just not
Zentaizo-attested. If `fetch` ever records paper/note content hashes (the
lock schema's standing TODO in `workspace-format.md`), `built_from` picks
them up with no schema change. Staleness is then a pure diff **scoped to the
recorded mode**: recompute the mode's input set, and a source in that set
whose current locked rev differs from its `built_from` entry (or which is
missing from `built_from` altogether — a newly added source) makes the graph
**stale**; `not_graphed` sources never do, and `status` surfaces them as a
count instead. `zentaizo status` gains one line:

```text
graph: built 2026-06-12 (graphify 1.4.2, code-only) — stale: 2 sources changed; 3 not graphed (--semantic)
```

(or `graph: not built — run 'zentaizo graph'` / `graph: current`). A stale
rebuild invokes Graphify's incremental `--update`; `zentaizo graph --force`
requests a from-scratch rebuild (passing Graphify's own `--force`, which also
covers the shrinking-graph case).

**`fetch` keeps the graph fresh itself — in code-only mode, never semantic**
(decided 2026-06-12, strengthened from "print a hint"; narrowed by Codex
review finding 1). A bare hint leaves the obvious gap of who acts on it and
when — but an implicit semantic refresh would make `fetch` a
model-API/cost/data-residency event. The code-only refresh is genuinely
local, deterministic, and fast, and its output is committed machine-derived
state — the same character as the lock `fetch` already rewrites; it is also
precisely the line upstream's own post-commit hook draws ("AST only, no API
cost"). So `fetch` auto-refreshes **code-only, best-effort** whenever a
`graph` block exists in the lock, the binary is on PATH, and at least one
included source's rev actually changed (no-op fetches stay silent). A graph
failure never fails the fetch — the same best-effort contract as the
commit-attribution hook installer. `zentaizo fetch --no-graph` opts out.
Semantic content is never auto-extracted: when changed sources include
docs/papers/notes of a graph last built `--semantic`, `fetch` prints the
explicit follow-up (`run 'zentaizo graph --semantic'`). The step-1 gate on
auto-patching `mode: semantic` graphs is **satisfied**: an AST-only
`graphify update` on a semantically-built graph was demonstrated to patch
code nodes while preserving every semantic node and edge — even with the
semantic cache deleted (preservation comes from incremental patching of the
existing `graph.json`). So `fetch` auto-refreshes code changes for graphs of
**either mode**; only semantic re-extraction stays explicit. The "graph now
stale — run `zentaizo graph`" hint also remains the fallback when
auto-refresh could not run (binary absent); the durable encoding for future
sessions is the `status` line plus the consultation bullet's
rebuild-if-stale clause, so the gap never silently widens.

Doc snapshots that are `flagged` by the safety pass are **excluded from the
input set** (and listed in the command output), matching `summarize`'s
quarantine rule — flagged content must not flow into derived layers.

### 5. Discovery: one consultation-order line in `workspace_agents()`

The "agents recognize it" piece *within a workspace* is a `cli.py` change to
the generated `AGENTS.md` (`workspace_agents()`, `cli.py:282`; order at
`cli.py:299-307`). The graph slots between summaries and docs:

1. `summaries/` for the big picture.
2. **When `graphify-out/graph.json` exists, ask the graph structural
   questions — `graphify query` / `path` / `explain` — especially for
   cross-repo relationships; check `graphify-out/GRAPH_REPORT.md` for the
   system's most-connected concepts. If `zentaizo status` reports the graph
   stale, run `zentaizo graph` first; skip a report `status` marks flagged.**
3. `docs/` … (unchanged)

Two sentences, deferring all mechanics to Graphify's own skill — consistent
with keeping generated instructions lean. The existing untrusted-input section
already covers the graph with no edit: the graph and report are *derived from*
untrusted fetched content, so they are evidence to cite, never instructions —
worth one parenthetical in the new bullet rather than a new section.

One verified operational footnote belongs next to the bullet: Graphify logs
every `query` / `path` / `explain` / MCP call to
`~/.cache/graphify-queries.log` by default (JSON Lines: timestamp, question,
corpus, node counts; full subgraph responses only if opted in). That is a
per-user file *outside* the workspace — against the "durable context stays
in the workspace" posture — so the generated bullet gains one clause for
sensitive workspaces: set `GRAPHIFY_QUERY_LOG_DISABLE=1` (or
`GRAPHIFY_QUERY_LOG=/dev/null`) when querying.

`zentaizo graph` should also print a post-build hint when the user-level skill
appears unregistered (best-effort check), pointing at `graphify install` — but
never run it: assistant-level registration is the user's call, not the
workspace's.

### 6. Sandbox interaction

The **code-only build** is a good sandbox citizen: local parsing, no network,
reads sources, writes only its output dir. In `compute_policy` terms
(`2026-05-30-sandboxing.md`), `graphify-out/` and the managed
`.graphifyignore` join the **writable set in both modes**, exactly like
`summaries/` — an implementing agent may rebuild a stale code-only graph
mid-task. Reference repos stay read-only inputs. **`--semantic` is not
sandbox-clean**: headless extraction needs network egress plus backend
credentials (or a local Ollama), so it is run by the human outside the
sandbox — or the agent achieves the same effect via the `/graphify` skill,
where extraction rides the agent's own session model and needs no extra keys
or egress beyond what the harness already grants.

## What is explicitly out of scope

- Wrapping `graphify query` / `path` / `explain` / MCP serving — Graphify-native.
- Registering Graphify's skill with assistants — `graphify install` does this
  at the user level.
- A summaries↔graph consistency check (interesting, speculative; revisit if
  drift is observed in practice).
- Graphing the workspace's own `sessions/` trail (a "process graph") — fun,
  not the system.
- Graphify's cross-project `--global` graph, `merge-graphs`, and `prs`
  surfaces — this plan is single-workspace graphing only.

## Build order

1. **Pin and verify the Graphify CLI surface** against a specific `graphifyy`
   version: where `graphify-out/` lands relative to CWD vs the scanned paths;
   how the post-commit hook invokes its AST-only rebuild (the default mode
   rides the same path if it is exposed; otherwise the managed ignore file
   excludes semantic file types); `.graphifyignore` priority/negation
   behavior at the workspace root; `graphify extract` `--update`/`--force`
   semantics and exit codes with and without a backend configured; **whether
   an AST-only `--update` on a `--semantic`-built graph preserves semantic
   nodes** (gates §4's auto-refresh for `mode: semantic`); **cache shape,
   typical size, and whether entries embed raw source chunks** (gates §3's
   commit-`cache/` default). The upstream facts above were verified against
   the raw v8 README on 2026-06-12, but the behavioral details need a local
   pass before any code. Sets the version floor for the extra.
   **Done 2026-06-12 — see "Step-1 findings (graphifyy 0.8.39)" below.**
2. `zentaizo graph [workspace] [--semantic] [--backend …] [--force]`: PATH
   gate, managed `.graphifyignore` generation, deterministic input set (§2,
   with flagged-doc exclusion), invoke `graphify update .` (code-only
   default) or `graphify extract . --backend …` + `cluster-only` (semantic
   opt-in), with `PYTHONHASHSEED=0` and `GRAPHIFY_NO_BACKUP=1` in the child
   env; run the docs-scan pass over `GRAPH_REPORT.md` with move-aside
   quarantine, write the lock `graph` block (§3–4).
3. `zentaizo status` graph line incl. mode, untracked sources, and
   `report_status` (§4) — `status_workspace`, `cli.py:1134`.
4. `fetch` best-effort **code-only** auto-refresh + `--no-graph` + the
   semantic follow-up and fallback hints (§4).
5. `workspace_agents()` consultation-order bullet (§5) and the `.gitignore`
   template changes: add `graphify-out/cost.json` and
   `docs/snapshots/*.flagged.*`; drop `docs/snapshots/` and `papers/*.pdf`
   (§2–3).
6. Docs: `workspace-format.md` (layout tree + a short Graph section beside
   Summaries), `cli.md`, README one-liner.
7. Sandbox: add `graphify-out/` **and the managed `.graphifyignore`** to the
   writable set in both modes, with sandbox-policy tests asserting both
   (§6).
8. Convention bump for existing workspaces flows through the existing
   `upgrade-zentaizo` skill path (regenerated `AGENTS.md` picks up §5), per
   the no-`zentaizo update` policy.

## Step-1 findings (graphifyy 0.8.39, verified 2026-06-12)

Verified locally against a scratch workspace mimicking the Zentaizo layout
(`repos/` with two repos incl. a nested `.gitignore`, `docs/snapshots/`,
`papers/`, `notes/`, `sessions/`, `summaries/`, `skills/`, `tmp/`), plus a
read of the installed package source where behavior needed a definitive
answer. Version floor: `graphifyy>=0.8.39`.

1. **Output placement.** `graphify update <path>` writes graph, report, html,
   and `cache/` to `<path>/graphify-out/`, but writes `manifest.json` to
   `$CWD/graphify-out/` keyed by CWD-relative paths — a 0.8.39 quirk that
   splits the output across two directories when CWD ≠ scanned path. With
   CWD = scanned path (`graphify update .`) everything coalesces, so
   **`zentaizo graph` runs the binary with CWD = workspace root and path
   `.`**. There is no multi-path invocation (one positional path); scoping is
   ignore-file-only. The output location is in fact configurable now
   (`extract --out DIR`, `GRAPHIFY_OUT` env var) — the plan's "upstream-fixed"
   premise is outdated — but Zentaizo still adopts the default
   `graphify-out/`: no reason to diverge.
2. **AST-only invocation path.** The post-commit hook launches
   `graphify.watch._rebuild_code()` — the same engine behind the
   **`graphify update <path>`** CLI verb ("re-extract code files... no LLM
   needed"). The default (code-only) mode invokes exactly that. Two
   refinements: `update` also performs **shallow markdown extraction**
   (file + heading nodes, zero tokens, fully offline), so the default mode is
   really "offline/no-LLM" rather than "code files only" — notes get
   structural nodes in both modes (and enter `built_from` as `"unfetched"` in
   both); PDFs and images are untouched without a backend. And the bare CLI
   does **not** pin `PYTHONHASHSEED` (the hook does, for deterministic
   louvain clustering), so `zentaizo graph` sets `PYTHONHASHSEED=0` in the
   child env to keep the committed `graph.json` reproducible.
3. **Ignore mechanics.** Per directory, `.graphifyignore` **replaces**
   `.gitignore` — the fallback reads `.gitignore` only when no
   `.graphifyignore` exists; they never merge. Consequently the managed file
   needs **no `!repos/` negation**: once it exists at the workspace root, the
   root `.gitignore` is simply not consulted, and `repos/` is visible by
   default. The flip side: the managed file must carry the workspace's full
   graph-exclusion set itself (`sessions/`, `summaries/`, `skills/`, `tmp/`,
   atlas + lock, `docs/snapshots/*.flagged.*`). Negation (`!`) does work
   (last-match-wins, with the gitignore parent-exclusion rule), and only the
   scan root's and its ancestors' ignore files are loaded — **nested ignore
   files are never read**, so a fetched repo's own `.gitignore` does not
   apply inside `repos/`; hygiene there rests on Graphify's built-in
   `_SKIP_DIRS` (node_modules, dist, build, target, venvs, framework caches,
   …), which in practice covers the heavy artifacts.
4. **The `snapshots` collision.** `_SKIP_DIRS` includes the literal names
   `snapshots` and `__snapshots__` (Jest/Vitest snapshot dirs). Skip-dir
   pruning runs before ignore evaluation and is unconditional: no
   `.graphifyignore` negation rescues it, `.graphifyinclude` is loaded but
   never applied in 0.8.39 (dead code), and there is no env override. So
   **`docs/snapshots/` cannot be graphed in 0.8.39 in either mode**. Doc
   snapshots are recorded in `not_graphed` with an explicit reason
   (`"skipped by graphify (snapshots dir)"`), `status` surfaces them in the
   not-graphed count, and the §2 input-set description is narrowed
   accordingly: the cross-source value in 0.8.39 is repos ↔ notes (+ papers
   under `--semantic`). Revisit when upstream wires `.graphifyinclude` or
   un-hardcodes the skip list.
5. **Semantic preservation — proven.** Built a semantic graph
   (`extract --backend claude-cli` over the scratch corpus), then modified
   code and ran AST-only `graphify update .`: all semantic nodes (rationale/
   concept) and their edges survived while the new code node appeared.
   Preservation holds **even with `cache/semantic/` deleted** — it comes
   from incremental patching of the existing `graph.json`, not the cache.
   **The §4 gate is satisfied: `fetch` auto-refresh applies to
   `mode: semantic` graphs too** (still code-only refresh; semantic
   re-extraction stays explicit).
6. **Cache contents — commit default finalized.** AST entries
   (`cache/ast/v<version>/<sha256>.json`, version-namespaced, auto-swept on
   upgrade) and semantic entries (`cache/semantic/<sha256>.json`,
   deliberately unversioned) both contain **extracted nodes/edges only — no
   raw source chunks** (verified in source and empirically). So `cache/` is
   **committed**, with one carve-out: `cache/stat-index.json` is a
   rebuildable stat memo holding absolute paths and nanosecond mtimes —
   machine-specific churn — and is **gitignored** alongside `cost.json`.
   Md content hashes strip YAML frontmatter before hashing.
7. **Reports.** `graphify update` writes `GRAPH_REPORT.md` on every build
   (offline, placeholder community names). Headless `graphify extract` does
   **not** write the report — it defers to `graphify cluster-only`, whose
   community naming wants an LLM. So `zentaizo graph --semantic` runs
   `extract --backend B` followed by `cluster-only . --backend B` (one small
   naming pass on the same explicit backend); the code-only path needs no
   second step.
8. **Dated backups.** Before overwriting a graph that is semantic
   (`.graphify_semantic_marker`) or human-curated, Graphify snapshots
   artifacts to `graphify-out/<YYYY-MM-DD>/`. In a workspace the committed
   graph's git history already serves that purpose, so `zentaizo graph` (and
   the fetch auto-refresh) set `GRAPHIFY_NO_BACKUP=1` to keep the output
   tree deterministic.
9. **Misc verified.** `extract` with no backend and no key exits 1 with a
   clear message ("A code-only corpus needs no key"); `--backend claude-cli`
   works against the local `claude` CLI with no API key; query logging
   defaults to `~/.cache/graphify-queries.log` with
   `GRAPHIFY_QUERY_LOG_DISABLE=1` / `GRAPHIFY_QUERY_LOG=<path>` overrides
   exactly as §5 describes; `GRAPHIFY_SKIP_HOOK=1` skips upstream's git
   hooks; `graphify-out/memory/` is force-included in scans; `update
   --force` / `GRAPHIFY_FORCE=1` covers the shrinking-graph case; a
   sensitive-file skip pass (`security.py`) runs during detection.

## Test plan

Zentaizo's logic is tested against a **stub `graphify` on PATH** — a script
that records its argv and writes canned `graphify-out/` content; the real
binary is exercised only in build step 1's manual verification pass. Named
cases (third Codex pass):

- **Binary gate:** missing `graphify` → nonzero exit, install commands
  printed, no lock mutation, no `graphify-out/`.
- **Managed `.graphifyignore`:** generated with marker comment; regenerated,
  not duplicated, on rebuild; carries the full workspace exclusion set
  (process trail, `tmp/`, atlas + lock, flagged snapshots — same content in
  both modes, since `.graphifyignore` replaces the root `.gitignore`
  wholesale); a user-owned `.graphifyignore` without the marker is
  refused, never overwritten (the hook-installer rule).
- **`.gitignore` template:** new workspaces get `graphify-out/cost.json`,
  `graphify-out/cache/stat-index.json`, and `docs/snapshots/*.flagged.*`;
  no longer get `docs/snapshots/` or `papers/*.pdf`; still get `repos/`
  and `tmp/`.
- **Lock semantics:** code-only build records `mode`, `built_from` covering
  exactly the graphed inputs (repos by rev, notes as `"unfetched"`),
  excluded sources in `not_graphed` mapped to reasons, no
  `semantic_backend`; `--semantic` without `--backend` errors; with it,
  records `semantic_backend`/`semantic_model` and moves papers into
  `built_from` as `"unfetched"`; doc snapshots stay in `not_graphed` in
  both modes (0.8.39 `snapshots` skip) with the skip reason.
- **Report quarantine:** flagged scan verdict → report moved to
  `GRAPH_REPORT.flagged.md`, nothing left at `GRAPH_REPORT.md`,
  `report_status: flagged` plus quarantine path in the lock.
- **Status line:** not built / current / stale, with the diff mode-scoped (a
  doc `content_hash` change does **not** stale a code-only graph); untracked
  and not-graphed counts; flagged-report surfacing.
- **Fetch integration:** auto-refresh fires only when a graphed source's rev
  changed; `--no-graph` skips; a failing stub never fails the fetch;
  `mode: semantic` graphs auto-refresh too (step-1 proof landed), with the
  semantic follow-up hint printed when semantic-typed sources changed.
- **Sandbox policy:** `compute_policy` output includes `graphify-out/` and
  the managed `.graphifyignore` as writable in both modes.

## Resolved questions (2026-06-12)

1. **Commit `graph.json`?** Yes. It turned out to be upstream's own model
   ("committed to git so everyone on the team starts with a map"), and the
   committed graph is what `--update` diffs against from a fresh clone.
   `cost.json` is gitignored and `manifest.json` committed; committing
   `cache/` is **finalized** by the step-1 inspection — entries hold
   extracted nodes/edges only, no raw source chunks — with
   `cache/stat-index.json` (machine-local stat memo) gitignored (§3).
2. **Safety pass over `GRAPH_REPORT.md`?** Yes — the same docs-scan pass as
   fetched docs, with move-aside quarantine to `GRAPH_REPORT.flagged.md` and
   the verdict recorded as `report_status` in the lock `graph` block (§3).
3. **Auto-suggest after `fetch`?** Resolved stronger than the original
   question, then narrowed by the Codex review: `fetch` auto-refreshes the
   graph best-effort **in code-only mode** when included revs actually
   changed; semantic re-extraction is always an explicit command, and the
   printed hint survives as the fallback when the binary is missing (§4).
4. **Commit fetched doc snapshots and papers?** (raised while resolving
   finding 2) Yes — the workspace `.gitignore` drops `docs/snapshots/` and
   `papers/*.pdf` and adds `docs/snapshots/*.flagged.*`. Papers have no
   fetcher, so gitignored papers were unrecoverable from a clone; committed
   snapshots pin exactly what the safety pass reviewed. `repos/` stays
   gitignored and is reached via the managed `.graphifyignore` instead (§2).
