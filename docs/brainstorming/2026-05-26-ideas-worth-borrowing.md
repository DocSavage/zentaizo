---
created: 2026-05-26
status: brainstorming
edited_by:
  - 2026-05-26  Claude Opus 4.7
  - 2026-05-30  Claude Opus 4.8
---

# Ideas worth borrowing

A living catalog of ideas from adjacent tools that *might* improve Zentaizo,
each kept here until it is either promoted into a real design doc / implemented,
or explicitly rejected. This is an idea backlog, not a commitment — entries are
hypotheses.

Per-entry shape:

- **Source** — where the idea came from.
- **The idea** — what the other tool does.
- **Maps onto** — the Zentaizo concept it would touch.
- **Why it might help / cost** — the trade.
- **Status** — `candidate` / `promoted to <doc>` / `rejected (reason)`.

---

## Seed: Context Hub (`chub`)

From comparing [Context Hub](https://github.com/andrewyng/context-hub) to
Zentaizo (full analysis and the integration mechanics in
`context-hub-integration-plan.md`). The structural difference framing the whole
list: chub is a **shared, agent-invoked, runtime-pull knowledge utility**;
Zentaizo is a **per-project, human-curated, git-committed workspace**. So the
ideas worth taking are the ones that survive that translation.

### 1. Resurfacing annotations

- **Source.** chub's `annotate <id> "note"`: an agent attaches a local note to a
  doc; it "persists across sessions and appears automatically on future
  fetches."
- **The idea.** Cheap, agent-authored, per-source notes that the system
  *guarantees* get re-shown the next time that source is consulted — a
  self-improving loop without any server.
- **Maps onto.** `notes/` and `summaries/sources/<name>.md`. Zentaizo has the
  storage but no convention that an agent-written per-source note is *always
  resurfaced* alongside the summary in the §2.5 consultation order. A
  `notes/sources/<name>.md` (or a fenced "agent notes" block in the source
  summary) that the consultation rule pins would close that gap. Pairs with the
  `[[link]]` cross-reference style already used in memory.
- **Why it might help / cost.** Highest-value idea on the list — it gives
  Zentaizo a learning loop that fits its git-native, decentralized model exactly.
  Cost: a convention + one line in `AGENTS.md` consultation order; near zero CLI.
- **Status.** candidate (strong).

### 2. `lang` / `version` fields on `docs` entries

- **Source.** chub's `--lang py|js` and `--version 19.1.0` variants.
- **The idea.** A doc source can pin language and version precisely.
- **Maps onto.** The `docs` entry schema in `workspace-format.md`. Adding optional
  `lang` and `version` lets one atlas say "FastAPI 0.115, Python" exactly —
  reinforcing the reproducibility Zentaizo already values via pinned refs. These
  are also the selectors the `chub` fetcher tier needs
  (`context-hub-integration-plan.md` §2.2), so the two land together.
- **Why it might help / cost.** Small schema add, real reproducibility win.
- **Status.** candidate.

### 3. Incremental / partial fetch as first-class

- **Source.** chub's `--file <ref>` (one reference file) vs `--full`, and the
  `references/` subdir model — fetch subsets to save tokens.
- **The idea.** Address *sections* of a large doc, not just whole files.
- **Maps onto.** Zentaizo's level-of-detail spine (summaries → docs → repos …).
  `fetch-docs` and `summarize` should be able to target sections of a big
  snapshot rather than always ingesting the whole thing — the same token
  instinct, expressed through the existing hierarchy.
- **Why it might help / cost.** Token efficiency on large API references. Cost:
  more moving parts in fetch/summarize; only worth it once snapshots get big.
- **Status.** candidate.

### 4. An explicit agent-facing retrieval verb

- **Source.** chub's whole "search → get → use" loop is designed for the *agent*
  to invoke (`chub search`, `chub get`), not the human.
- **The idea.** A crisp query surface the agent calls, rather than "go read files
  under `docs/`."
- **Maps onto.** A thin, read-only `zentaizo get <source> [--section]` (and maybe
  `zentaizo search <query>`) over already-fetched workspace content. Stays within
  the thin-CLI rule (no network, no judgment — just locate-and-print), but gives
  agents a sharper entry point than filesystem spelunking, and a natural place to
  surface idea #1's resurfacing notes.
- **Why it might help / cost.** Better agent ergonomics; risk of duplicating what
  plain file reads already do — only worth it if it adds value (section
  addressing, note resurfacing, provenance) over `cat`.
- **Status.** candidate (evaluate after #1).

### 5. Workspace → shareable content export

- **Source.** chub's local content path: `chub build my-content/ -o .chub-local/`
  + `~/.chub/config.yaml` `sources:` pointing teammates at a shared dir.
- **The idea.** A team points many agents at one curated, offline content tree.
- **Maps onto.** Exporting `summaries/sources/<name>.md` into chub's
  `<pkg>/docs/<topic>/<lang>/DOC.md` format so a Zentaizo workspace becomes a
  private chub source (detailed as Part 3 of `context-hub-integration-plan.md`).
  More broadly: the *idea* of a workspace publishing its distilled knowledge for
  other agents/teams to consume is worth holding onto even independent of chub.
- **Why it might help / cost.** Turns per-workspace curation into shared
  infrastructure. Cost: format coupling to an external tool; defer.
- **Status.** candidate (future).

### Explicitly **not** borrowing (for now)

- **Global ratings / feedback-to-maintainers loop** (chub's `feedback up|down`).
  It only pays off with a central registry and a maintainer community to receive
  the signal — neither exists in Zentaizo's decentralized, per-workspace model.
  The *local* half of chub's loop (annotations, idea #1) is the part that
  translates; the *global* half does not.
- **Inheriting chub's "curated registry ⇒ trusted content" posture.** Rejected on
  principle — Zentaizo treats all fetched docs as untrusted injection surface
  (`api-reference-docs-layer.md` §2.9). Noted here so the boundary is explicit,
  not re-litigated later.

---

## Seed: Agent-harness sandboxes

From comparing how the coding harnesses confine themselves — Claude Code's
`permissions` config + devcontainer, Codex's OS sandbox (Landlock/seccomp on
Linux, Seatbelt on macOS) with `read-only`/`workspace-write` modes, and Gemini
CLI's Docker/Podman `--sandbox`.

### 6. Atlas-driven least-privilege execution

- **Source.** The per-harness sandbox/permission models above.
- **The idea.** Confine an agent to least-privilege access — write only where it
  should, read the rest, escape nothing — enforced either by harness config or by
  an OS-level container.
- **Maps onto.** The `role: "edit"` / `role: "reference"` split, which *already*
  encodes the policy (writable = `sessions/` + editable repos; read-only =
  reference repos; deny outside the workspace). Zentaizo can render that one
  policy into each harness's config, or into container mount permissions.
- **Why it might help / cost.** Recovers the "edit/reference drives sandbox
  isolation" idea, and lets the maintainer run agents at the workspace level with
  the reference repos genuinely read-only. Cost: harness-config enforcement is
  best-effort (a shell redirect escapes file-tool denies); only a container is
  airtight, and containers add a runtime dependency + per-harness ergonomics.
  Resolved by keeping `zentaizo sandbox` (config) in the thin core and
  `zentaizo-containers` (OS-level) as an opt-in allied repo.
- **Status.** promoted to `sandboxing.md`.

---

## Adding to this doc

When a new tool comparison surfaces ideas, add a `## Seed: <tool>` section with
entries in the per-entry shape above. When an idea graduates, change its
**Status** to `promoted to <doc>` and leave the entry as a breadcrumb rather than
deleting it. When an idea is rejected, record the reason — a rejected idea with a
reason is more useful than a silently dropped one.
