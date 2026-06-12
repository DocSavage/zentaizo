---
created: 2026-06-12
status: proposed
edited_by:
  - 2026-06-12  Claude Fable 5
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

## Context — what Graphify is

Graphify ([repo](https://github.com/safishamsi/graphify),
[site](https://graphify.net/)) is a Python CLI (PyPI package `graphifyy`,
command `graphify`) that parses a folder of code, SQL, docs, PDFs, and images
locally via tree-sitter — zero API calls — and builds a queryable knowledge
graph. As of mid-2026 it is widely adopted (tens of thousands of GitHub stars,
1M+ PyPI downloads; YC S26).

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
- `cache/`, `cost.json` — per-run working state (upstream's recommended
  `.gitignore` entries)

Graph state is **directory-local** — there is no user-level or global cache.
Upstream's docs say `graphify-out/` "is meant to be committed to git so
everyone on the team starts with a map", and `graphify <path> --update`
re-extracts only changed files, diffing against the existing committed graph.
The build's output location is not configurable (only
`graphify export … --output` takes a path), so the directory name
`graphify-out/` is fixed.

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
(`graphify install`), the build engine, and the entire query surface
(`query` / `path` / `explain` / MCP). None of that is wrapped.

**Zentaizo owns** the workspace conventions Graphify cannot know:

1. *What to graph* — which parts of the workspace are system sources and which
   are process trail (sessions/, derived summaries) that would pollute the
   graph.
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
graph = ["graphifyy>=X.Y"]   # pin the floor once the CLI surface is verified
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
inside Zentaizo's own environment — and exits nonzero. Note that
`graphify install` (per-assistant skill registration) is *not* required for
workspace use: inside a workspace the generated `AGENTS.md` gives the agent
the query commands directly, so only the binary matters here.

### 2. Input set: primary sources only

`zentaizo graph` computes the include set deterministically from the workspace
layout — this is the main reason a CLI verb beats a documented convention (the
"CLI is deterministic; the assistant exercises judgment" principle from the
summarize design; without the verb every agent re-derives the include/exclude
list and nothing records provenance):

- **Included:** `repos/`, `docs/`, `papers/`, `notes/` — the four primary
  source trees.
- **Excluded:** `sessions/` (workspace process trail, not the system),
  `summaries/` (derived prose; graphing a derivative alongside its sources
  creates edges between text *about* the system and the system), `skills/`,
  `tmp/`, the graph output dir itself, and `.git` internals.

One graph for the whole workspace, not per-source subgraphs — the cross-source
edges are the point (§ Why this maps). A per-source opt-out knob in the atlas
(e.g. `graph: false` on a huge reference repo) is deliberately **not** added
until a real workspace needs it: explicit boring JSON, but not preemptive
JSON.

### 3. Output location and commit policy

Graphify's build output location is not configurable, so the workspace adopts
**`graphify-out/` at the workspace root** as-is rather than fighting the tool
(`zentaizo graph` runs from the root; the lock records the observed
`output_dir`, and build step 1 confirms exactly where the directory lands
relative to the scanned paths):

```text
graphify-out/
  graph.json        # committed — machine-derived, like the lock
  GRAPH_REPORT.md   # committed — markdown context, like a summary
  graph.html        # committed — regenerable, but upstream ships it as part of the map
  cache/            # gitignored — per-run working state
  cost.json         # gitignored — per-run working state
```

Commit policy (decided 2026-06-12): **commit the graph, gitignore only
`cache/` and `cost.json`** — exactly upstream's recommended split
("`graphify-out/` is meant to be committed to git so everyone on the team
starts with a map"). Committing `graph.json` is what makes the layer
workspace-local in the Zentaizo sense: a fresh clone has the graph
immediately, `--update` diffs against the committed state instead of
rebuilding from scratch, and the graph travels with the lock that vouches for
it. The workspace `.gitignore` template gains the two `graphify-out/` entries.

**`GRAPH_REPORT.md` goes through the same docs-scan safety pass** that
`fetch-docs` applies (decided 2026-06-12; no exception for locally-generated
content — it is deterministic extraction *from* untrusted sources, and it is
the one artifact agents read as prose). The verdict is recorded as
`report_status: ok | flagged` in the lock `graph` block; a flagged report is
surfaced by `zentaizo status` and skipped by agents (the consultation bullet
says so) — the same quarantine posture flagged doc snapshots get.

### 4. Lock provenance and staleness

`zentaizo graph` records a top-level `graph` block in `zentaizo.lock.json`
after a successful build:

```json
"graph": {
  "backend": "graphify",
  "backend_version": "1.4.2",
  "built_at": "2026-06-12T15:04:11Z",
  "output_dir": "graphify-out",
  "report_status": "ok",
  "built_from": {
    "repos/shortener-api": "9f3a1c4e7b…",
    "docs/api-docs": "sha256:…"
  }
}
```

`built_from` maps each included source to the same locked identity
`summarize` pins (`repo` commit/head; doc snapshot `content_hash`) — the lock
stays the single source-state oracle, no second record is invented. Staleness
is then a pure diff: a source whose current locked rev differs from its
`built_from` entry (or a source absent from `built_from`) makes the graph
**stale**. `zentaizo status` gains one line:

```text
graph: built 2026-06-12 (graphify 1.4.2) — stale: 2 sources changed since build
```

(or `graph: not built — run 'zentaizo graph'` / `graph: current`). A stale
rebuild invokes Graphify's incremental `--update`; `zentaizo graph --force`
requests a from-scratch rebuild (passing Graphify's own `--force`, which also
covers the shrinking-graph case).

**`fetch` keeps the graph fresh itself** (decided 2026-06-12, strengthened
from "print a hint"). A bare hint leaves the obvious gap of who acts on it
and when. The rebuild is local, deterministic, fast (`--update`), and its
output is committed machine-derived state — the same character as the lock
`fetch` already rewrites — so `fetch` auto-refreshes the graph
**best-effort** whenever a `graph` block exists in the lock, the binary is on
PATH, and at least one included source's rev actually changed (no-op fetches
stay silent). A graph failure never fails the fetch — the same best-effort
contract as the commit-attribution hook installer. `zentaizo fetch
--no-graph` opts out. The "graph now stale — run `zentaizo graph`" hint is
the fallback, printed only when auto-refresh could not run (binary absent);
the durable encoding for future sessions is the `status` line plus the
consultation bullet's rebuild-if-stale clause, so the gap never silently
widens.

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

`zentaizo graph` should also print a post-build hint when the user-level skill
appears unregistered (best-effort check), pointing at `graphify install` — but
never run it: assistant-level registration is the user's call, not the
workspace's.

### 6. Sandbox interaction

The graph build is a good sandbox citizen: local parsing, no network, reads
sources, writes only its output dir. In `compute_policy` terms
(`2026-05-30-sandboxing.md`), `graphify-out/` joins the **writable set in
both modes**, exactly like `summaries/` — an implementing agent may rebuild a
stale graph mid-task. Reference repos stay read-only inputs.

## What is explicitly out of scope

- Wrapping `graphify query` / `path` / `explain` / MCP serving — Graphify-native.
- Registering Graphify's skill with assistants — `graphify install` does this
  at the user level.
- A summaries↔graph consistency check (interesting, speculative; revisit if
  drift is observed in practice).
- Graphing the workspace's own `sessions/` trail (a "process graph") — fun,
  not the system.

## Build order

1. **Pin and verify the Graphify CLI surface** against a specific `graphifyy`
   version: where `graphify-out/` lands relative to CWD vs the scanned paths,
   whether one invocation accepts multiple paths (or needs an
   exclude mechanism over the workspace root), `--update`/`--force`
   semantics, `--version`, exit codes. The README-level facts above are from
   upstream docs and need a local pass before any code. Sets the version
   floor for the extra.
2. `zentaizo graph [workspace] [--force]`: PATH gate, deterministic input set
   (§2, with flagged-doc exclusion), invoke build/`--update`, run the
   docs-scan pass over `GRAPH_REPORT.md`, write the lock `graph` block
   (§3–4).
3. `zentaizo status` graph line incl. `report_status` (§4) —
   `status_workspace`, `cli.py:1134`.
4. `fetch` best-effort auto-refresh + `--no-graph` + fallback hint (§4).
5. `workspace_agents()` consultation-order bullet (§5) and the `.gitignore`
   template entries (§3).
6. Docs: `workspace-format.md` (layout tree + a short Graph section beside
   Summaries), `cli.md`, README one-liner.
7. Sandbox: add `graphify-out/` to the writable set (§6).
8. Convention bump for existing workspaces flows through the existing
   `upgrade-zentaizo` skill path (regenerated `AGENTS.md` picks up §5), per
   the no-`zentaizo update` policy.

## Resolved questions (2026-06-12)

1. **Commit `graph.json`?** Yes. It turned out to be upstream's own model
   ("committed to git so everyone on the team starts with a map"), and the
   committed graph is what `--update` diffs against from a fresh clone. Only
   `cache/` and `cost.json` are gitignored (§3).
2. **Safety pass over `GRAPH_REPORT.md`?** Yes — the same docs-scan pass as
   fetched docs, verdict recorded as `report_status` in the lock `graph`
   block, flagged reports quarantined from agent reading (§3).
3. **Auto-suggest after `fetch`?** Resolved stronger than the original
   question: `fetch` auto-refreshes the graph best-effort when included revs
   actually changed; the printed hint survives only as the fallback when the
   binary is missing (§4).
