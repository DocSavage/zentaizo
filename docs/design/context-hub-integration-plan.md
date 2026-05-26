# Context Hub (`chub`) integration plan

## Context

[Context Hub](https://github.com/andrewyng/context-hub) (Andrew Ng / aisuite) is
a CLI that gives coding agents curated, versioned, language-specific API
reference docs from a shared community registry. It overlaps directly with the
API/reference-docs layer specced in `api-reference-docs-layer.md` (§2.3's
pluggable doc fetcher), but sources content from a registry rather than by
crawling upstream sites.

This document covers two things:

1. **How to install and use `chub` standalone** — the verbatim commands, content
   model, and the local/offline "bring your own docs" path.
2. **How we would expose it as an optional fetcher tier, `zentaizo[docs-chub]`** —
   so a Zentaizo workspace can pull a registry doc into `docs/snapshots/` through
   the same safety pass and lock machinery as every other doc source.

The design follows the standing repo philosophy (`AGENTS.md`): **keep the CLI
thin and deterministic, prefer the best backend that is installed, fail safe to
reference-only.** `chub` is a fetcher *tier*, never a hard dependency.

---

## Part 1 — Using `chub` directly

### Install

```bash
npm install -g @aisuite/chub
```

It is an **npm/Node** package and is "designed for your coding agent to use (not
for you to use!)" — agents call it mid-task to retrieve current API docs.

### Commands

| Command | Purpose |
|---|---|
| `chub search "stripe"` | locate docs/skills by query |
| `chub get stripe/api` | fetch a doc by `<package>/<topic>` id |
| `chub get stripe/api --lang js` | fetch a language variant (`py`, `js`, …) |
| `chub get stripe/api --version 19.1.0` | fetch a pinned version |
| `chub get stripe/api --file <ref>` | fetch one reference file (incremental, token-cheap) |
| `chub get stripe/api --full` | fetch the complete doc |
| `chub annotate stripe/api "note"` | attach a local note that resurfaces on future `get` |
| `chub annotate stripe/api --clear` / `chub annotate --list` | manage annotations |
| `chub feedback stripe/api up\|down` | rate a doc; ratings flow to maintainers |

It also ships a Claude/Cursor skill (`skills/get-api-docs/SKILL.md`) you can copy
into `.claude/skills/` or `.cursor/rules` so an agent knows to reach for it.

### Content model

Registry content lives at a predictable path:

```text
content/<package>/docs/<topic>/<lang>/DOC.md
  content/aiohttp/docs/package/python/DOC.md   # id: aiohttp/package, lang py
  content/aiohttp/docs/cors/python/DOC.md       # id: aiohttp/cors
  content/stripe/docs/api/javascript/DOC.md     # id: stripe/api, lang js
```

A doc id is `<package>/<topic>`; `--lang` and `--version` select the variant. A
`references/` subdir alongside `DOC.md` holds the extra files that `--file`
fetches incrementally. Each `DOC.md` is **plain markdown with YAML frontmatter**:

```yaml
---
name: package
description: "aiohttp package guide for Python - async HTTP client/server, web apps, and websockets"
metadata:
  languages: "python"
  versions: "3.13.3"
  revision: 1
  updated-on: "2026-03-11"
  source: maintainer
  tags: "aiohttp,python,asyncio,http,web,websocket,client,server"
---
```

Content is community-maintained: API/framework authors submit docs as **pull
requests** to the central registry.

### Local / private content (the offline path — important for us)

`chub` is not registry-only. You can build a local content tree and point config
at it:

```bash
chub build my-content/ -o .chub-local/
```

```text
my-content/
  mycompany/
    docs/
      internal-api/
        DOC.md
```

```yaml
# ~/.chub/config.yaml
sources:
  - name: internal
    path: /path/to/.chub-local
```

> "Put your content directory in a shared git repo or internal CDN. Everyone on
> the team points their config at it."

This means `chub` can serve content **fully offline from a local path**, with no
call to the central registry — which is what makes a clean, network-free
integration possible (and opens the bidirectional idea in Part 3). (A separate
hosted "private content" feature is marked *Coming Soon* in their docs; we rely
only on the local `chub build` path, which exists today.)

---

## Part 2 — `zentaizo[docs-chub]` as a fetcher tier

### 2.1 The Node-dependency wrinkle (decide first)

Every existing extra (`docs-scan` = `llm-guard`, and the planned `docs`/`docs-rich`)
is a **pip-installable Python package**. `chub` is **npm**, so it cannot be pulled
in via `pip install zentaizo[docs-chub]`. Two honest options:

- **(Recommended) Marker extra + PATH detection.** `[docs-chub]` installs no
  Python package (or only a trivial adapter shim); the fetcher tier shells out to
  a `chub` binary the user installed separately (`npm install -g @aisuite/chub`).
  If `chub` is absent from `PATH`, the tier is simply skipped — exactly the
  "best backend that is installed" pattern from `api-reference-docs-layer.md`
  §2.3, and the fail-safe is reference-only. The extra then exists mostly to
  document intent and to let us pin a compatible `chub` version range in the
  lock.
- Vendor nothing and document the `npm` step in `curate-atlas` guidance, dropping
  the extra entirely.

Recommendation: keep a thin `[docs-chub]` marker extra for discoverability, but
make the real gate "is `chub` on `PATH`," not "is a Python package installed."

### 2.2 Atlas schema — a third doc-source discriminator

`api-reference-docs-layer.md` §2.1 gives a `docs` entry exactly one of `url` or
(`repo`+`path`). Add a third, mutually-exclusive form: a `chub` id plus optional
variant selectors.

```json
{
  "name": "stripe-api",
  "kind": "api-reference",
  "chub": "stripe/api",
  "lang": "py",
  "version": "19.1.0",
  "description": "Stripe API reference, pulled from Context Hub"
}
```

`validate` gains: a `docs` entry has **exactly one** source discriminator —
`url`, (`repo`+`path`), or `chub` — and the `chub` value must look like
`<package>/<topic>`.

`lang` and `version` are **generic, optional doc-variant fields valid on any
`docs` entry**, not chub-scoped (this is idea #2 in `ideas-worth-borrowing.md`):
they pin "which language / which release" for an external `url` doc just as
usefully as for a `chub` id. The chub fetcher tier simply *consumes* them as
`chub get` selectors when present; other tiers may use them as provenance/hints.
Resolving the scope here — rather than deferring it — is the point: the field
semantics are owned by this plan, and `workspace-format.md` is updated to match
as the §2.5 implementation step, not as a separate design decision.

### 2.3 Where it sits in the `fetch-docs` cascade

`chub`-sourced entries get their own tier, ahead of crawling because the content
is already LLM-shaped markdown:

1. If the entry has a `chub` id **and** `chub` is on `PATH`:
   run `chub get <id> [--lang <lang>] [--version <version>] --full` and capture
   stdout into `docs/snapshots/<name>.md`.
2. Run the captured markdown through the **§2.9 safety pass before writing it
   into the workspace** (see 2.4) — no exception for registry content.
3. Record provenance in the lock (2.5).
4. If `chub` is absent or `get` fails, fall through to the normal cascade
   (`llms.txt` → single-page → reference-only), and on total failure keep the
   entry as **reference-only** with reason `no-source` (binary absent) or
   `fetch-error` (binary present but failed), per §2.3 tier 4.

Like all of Part 2 of the docs layer, this lives behind `zentaizo fetch-docs`,
not `zentaizo fetch`.

### 2.4 Safety — do **not** inherit chub's trust model

`chub` content is PR-reviewed, but it is still third-party markdown that we
**commit to git and re-read in every future session** — the exact durable
indirect-prompt-injection surface that `api-reference-docs-layer.md` §2.9 is
about. So:

- A `chub` snapshot is tagged **untrusted external** like any other, runs the
  full sanitize → flag → quarantine pass, and is preferred-via-`summaries/` at
  consultation time (§2.5).
- We adopt none of chub's "the registry is curated, therefore trusted"
  assumption. Curation reduces, not eliminates, the risk; our architectural
  controls remain load-bearing.

### 2.5 Lock + workspace-format

Per doc source with a `chub` origin, record: the `chub` id, resolved `lang` and
`version`, the source `revision`/`updated-on` lifted from the snapshot
frontmatter, snapshot path, content hash, `fetched_at`, `fetcher: chub`, the
resolved `chub` CLI version, and the snapshot status (`ok` /
`reference-only:no-source` / `reference-only:fetch-error` / `flagged`). This
makes a registry pull as reproducible/diffable as a pinned git ref. Document the
`chub` discriminator and these fields in `workspace-format.md`.

### 2.6 Discovery (`curate-atlas` / `discover-docs`)

When inventorying a repo, if a dependency (from `pyproject.toml`,
`package.json`, etc.) matches a `chub search` hit, `curate-atlas` can suggest a
`chub`-sourced `docs` entry instead of hunting for a doc site. This is judgment
work, so it belongs in `skills/curate-atlas.md`; `discover-docs` could
optionally run `chub search` for top-level deps and print candidates (network +
optional binary, so gate it behind a flag to preserve the read-only/offline
default).

---

## Part 3 — Bidirectional: workspace → chub content (future)

Because `chub build my-content/ -o .chub-local/` ingests a local
`<pkg>/docs/<topic>/<lang>/DOC.md` tree, a Zentaizo workspace's
`summaries/sources/<name>.md` could be **exported into chub content format** and
served back to agents via `chub get`, with the workspace pointing its own
`~/.chub/config.yaml` at the generated `.chub-local`. That turns a Zentaizo
workspace into a private, team-shareable chub source. Out of scope for v1;
tracked as an idea in `ideas-worth-borrowing.md`.

---

## Open decisions

1. **Node dependency posture.** Marker extra + PATH detection (recommended) vs
   no extra at all. (§2.1)
2. **Snapshot vs live reference.** Commit the `chub get --full` output as a
   snapshot (recommended — matches Zentaizo's reproducible-commit model, record
   `revision`/`version`) vs keep it reference-only and re-pull at use-time
   (matches chub's runtime-pull model but loses reproducibility).
3. **Trust.** Treat chub content as untrusted external like all snapshots
   (recommended) vs a lighter pass for registry-sourced content. (§2.4)
4. **`--full` vs incremental `--file`.** Pull the whole doc once (recommended for
   a committed snapshot) vs mirror chub's incremental model into the level-of-detail
   spine (more faithful to chub, more moving parts).
5. **Export direction (Part 3).** Build it now vs defer.

## Suggested build order

1. Atlas `chub` discriminator + `validate` (2.2). Small, no new dependency.
2. `[docs-chub]` marker extra + PATH detection + the `chub get` fetcher tier
   wired through the existing safety seam and lock schema (2.1, 2.3, 2.4, 2.5).
3. `curate-atlas` / `discover-docs` probing (2.6).
4. Workspace → chub export (Part 3), if pursued.

## Sources

- [Context Hub repo](https://github.com/andrewyng/context-hub) and its
  `README.md`, `cli/README.md`, `docs/byod-guide.md`, `docs/content-guide.md`,
  `docs/feedback-and-annotations.md`, `docs/features/agent-annotations.md`.
- Content layout observed under `content/<pkg>/docs/<topic>/<lang>/DOC.md` and
  the `aiohttp` frontmatter example.
- Cross-references: `api-reference-docs-layer.md` (the fetcher cascade, safety
  pass, lock schema this plugs into) and `ideas-worth-borrowing.md`.
