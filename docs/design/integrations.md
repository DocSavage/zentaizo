# External Knowledge Integrations

_Distilled design doc — current architecture + rationale._

## What it is

Zentaizo keeps its CLI thin and deterministic while delegating specialized work
to bounded library integrations. Baseline integrations that are Python-native
and required by the standard workflow ship as core dependencies; heavy,
model-backed, or separately distributed capabilities remain opt-in. Every
boundary fails safe (a deterministic fallback, reference-only result, or a clear
install hint). The CLI owns workspace conventions (what to include, where output
lives, how provenance and staleness are tracked) and delegates the heavy lifting
to the external tool.

No external knowledge integration ships today. The Graphify knowledge-graph
layer (`zentaizo graph`) shipped through 0.18.0 and was removed in 0.19.0. The
section below says why, and how to run Graphify by hand. A second direction,
sourcing API reference docs through Context Hub, is an open proposal and is not
implemented.

## Architecture

### Graphify (removed in 0.19.0)

Through 0.18.0, `zentaizo graph` built one
[Graphify](https://github.com/safishamsi/graphify) knowledge graph over the
whole workspace. The generated `AGENTS.md` told agents to query it, `fetch`
refreshed it, `bring-up` built it, and `status` reported on it. Release 0.19.0
(conventions generation 7) removed all of it: the command, those steps, the
graph text in generated files, the lock's `graph` block, the managed
`.graphifyignore`, and the `graphifyy` dependency.

Measured use showed that agents gained nothing from the graph:

- In 44 Claude Code sessions on one machine, Claude never queried the graph.
  Every `graphify` command Claude ran was upkeep, such as `--version` or
  `update --force`.
- Codex made 10 graph queries across 5 sessions. Five returned nothing useful,
  three repeated a text search Codex had just run, and two gave a line number
  in a file Codex already had open. Running `rg -n` on that file would have
  given the same line.

The upkeep was real. On one development machine, 8 of 10 workspaces held a
`graphify-out/` of 97 MB to 2.3 GB, about 5.6 GB in all (survey of
2026-11-03). The pinned dependency shipped 259 releases in 6.5 months.

To run Graphify on a workspace by hand:

1. Install it yourself, for example with `pipx install graphifyy`. The package
   is `graphifyy`; the command it installs is `graphify`.
2. Put `!repos/` in a `.graphifyignore` at the workspace root. Graphify also
   reads `.gitignore` and `.git/info/exclude` (checked in 0.9.86), and this
   line makes it scan `repos/` even though `.git/info/exclude` hides `repos/`
   from git.
3. Keep `graphify-out/` out of git with a line in `.git/info/exclude`. That
   file belongs to the local clone, so the shared `.gitignore` stays as
   Zentaizo generates it.
4. From the workspace root, build the graph with `graphify update .`, then
   query it with `graphify query`, `graphify path` and `graphify explain`.

For one release, `zentaizo graph` remains as a stub that prints the removal
notice and exits 2, and `zentaizo fetch --no-graph` is accepted as a no-op
with a deprecation notice. A later MINOR release removes both.

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
current-API-docs-for-agents service). Whether chub earns its own tier, or
whether an existing doc fetcher already covers the need, is an open question,
not a decision.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Integration shape | Bundle deterministic Python-native baseline tools; keep heavy/model-backed capabilities optional | Standard setup works after one package install without silently adding heavyweight scanners |
| Graphify graph layer | Removed in 0.19.0; a one-release `graph` stub and `fetch --no-graph` no-op | Measured use showed no gain over text search, against real disk and dependency upkeep |
| Context Hub | Proposed only — not implemented | Open direction pending a Context7 comparison |

## Considered and not taken

- **Keeping the graph as an opt-in layer** — an opt-in path would still keep
  the graph code, the lock `graph` block and the managed `.graphifyignore`,
  all tracking a dependency that shipped 259 releases in 6.5 months, for use
  that measurably added nothing. Anyone who wants a graph can run Graphify by
  hand, as above.
- **Treating Context Hub registry content as pre-trusted** — would not be
  adopted even if chub ships; curation reduces, not eliminates, prompt-injection
  risk.

## See also

- `CHANGELOG.md` — the removal entry (conventions generation 7).
- `src/zentaizo/templates/global-skills/zentaizo/upgrade-zentaizo.md` — the
  generation-7 steps that delete a workspace's graph artifacts.
- `docs/cli.md` — the `zentaizo graph` stub and `zentaizo fetch --no-graph`.
