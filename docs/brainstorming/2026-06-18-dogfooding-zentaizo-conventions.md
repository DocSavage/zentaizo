---
created: 2026-06-18
status: promoted
promoted_to: ../changes/2026-06-19-dogfooding-zentaizo-conventions.md
edited_by:
  - 2026-06-18  Claude Opus 4.8 (1M context)
  - 2026-06-18  Bill Katz, Claude Opus 4.8 (1M context)
  - 2026-06-19  Claude Opus 4.8 (1M context)
---

# Should the Zentaizo tool repo adopt Zentaizo workspace conventions (and an atlas)?

_Brainstorm / idea backlog — hypotheses, not commitments. Prompted by a request
to "foster the ability to improve the Zentaizo tool repo" by having it adopt the
workspace conventions it generates: a `sessions/` trail (`brainstorming`,
`changes`, `debugging`, `efforts`, `handoffs`, `questions`, `reports`), and
possibly its own atlas + `repos/`/`docs/` — used **in conjunction with**
[`ideas-worth-borrowing.md`](2026-05-26-ideas-worth-borrowing.md). This note
lays out the option space before we review and write an implementation slice._

## The elephant: AGENTS.md currently says "not a workspace"

`AGENTS.md:11-15` is explicit today:

> This is the **Zentaizo tool repo** — the CLI and workspace *format*. You are
> developing the tool that generates workspaces; this is **not** itself a
> workspace, so there is no `zentaizo.atlas.json`, `summaries/`, or `sessions/`
> trail to curate here. The global Zentaizo skill describes how to *use* a
> workspace — do not follow it as a workflow when working in this repo.

So this proposal is a **deliberate reversal of a stated stance**, not a
greenfield decision. Whatever we adopt, the win has to be worth rewriting that
paragraph — and the doc has to say *which* conventions apply here and which
still don't, so the next agent isn't left guessing.

## What the repo already has (partial adoption)

The before/after split is already here, just not under `sessions/`:

- `docs/brainstorming/` — pre-decision exploration (this file's home).
- `docs/changes/` — dated design docs for decided changes
  (`YYYY-MM-DD-<slug>.md`), with `created` / `status` / `implemented` (+ sha) /
  `edited_by` frontmatter.

`AGENTS.md:33-34` already frames these as "the same before/after split a
workspace's `sessions/` uses." So the question is not "start from zero" — it is
**how much further to go, and in what shape.**

The gap versus a real workspace: no `efforts.json` registry, no
effort-scoped slice filenames (`<label>-NNNN-<slug>.md`), no
`debugging/`/`questions/`/`handoffs/`/`reports/` charters, no atlas, no
`repos/`/`docs/`/`summaries/` source layer, no lock, no graph. And the repo's
`docs/changes/` files are **freeform dated design docs**, not CLI-allocated,
effort-scoped slices — adopting the workspace convention changes their filename
and frontmatter schema.

## Why a workspace exists — and why *one* editable repo changes the calculus

The reason to stand up a separate zen workspace at all is that brainstorming and
implementation **cut across many repos**. Cross-repo meta-work — design
discussions, the approaches considered, the implementation plans, the record of
what was *rejected* — has no natural home in any single editable repo:
committing it into repo A arbitrarily privileges A over B and C, and scatters one
coherent design narrative across repositories that each see only their slice. The
workspace is the **neutral cross-cutting home** that removes that forced choice.

That rationale **dissolves when a workspace has exactly one editable repo** (all
others `reference`) — which is precisely zentaizo's shape. With one editable repo
there is no "which repo owns the meta-trail?" question: the one editable repo is
the obvious, only home. So a single-editable-repo workspace can keep its
meta-analyses and plans **inside that repo, as design documentation of itself**,
including a first-class *record of brainstorming that was never implemented*
(exactly the audit that prompted this doc — the most useful thing a future
contributor can read is *why the obvious path was rejected*). This is a general
property, not a zentaizo quirk; it is the principled trigger for in-repo
adoption and the reason Options C/D below are attractive at all.

## The core structural mismatch (the thing to design around)

A generated workspace and this repo are inside-out relative to each other:

- **A workspace** is a *context* repo at the root (atlas + summaries +
  `sessions/`, its own git history) with the **editable code vendored under
  `repos/<name>/`** (gitignored clones). `zentaizo create` scaffolds exactly
  this (`create_workspace`, `cli.py:842-885`: `repos/ docs/ papers/ notes/
  summaries/ sessions/{efforts,brainstorming,changes,questions,debugging,handoffs,reports}`,
  with `repos/` in `.gitignore`).
- **This repo** *is* the editable code at the root. There is nothing to vendor
  into `repos/` — the thing being edited is `src/zentaizo/`.

Four concrete collisions follow from that inversion, and any in-repo option has
to answer each:

1. **Self-vendoring recursion.** An atlas that lists zentaizo as an `edit` repo
   would clone the repo into `repos/zentaizo/` *inside the repo* — a workspace
   nested in the thing it describes. Avoidable only by not treating zentaizo as
   an atlas source (edit in place) or by hosting the workspace elsewhere.
2. **The commit-separation rule breaks.** `workspace_agents()` (`cli.py:403`)
   tells agents to "commit workspace notes/plans separately from editable-repo
   code — they live in different repositories." Here they'd be the **same**
   repo: `sessions/` notes and `src/` code share one git history. The rule
   either gets dropped or reinterpreted (e.g. separate *commits*, not separate
   repos).
3. **Sandbox / lock semantics assume `repos/`.** `compute_policy`
   (`cli.py:4406`) derives writable vs. read-only from the atlas `role` split
   over `repos/`; the lock records resolved editable-repo SHAs. With the code at
   the root and no editable atlas source, both layers have nothing to bite on.
4. **Summaries summarize *sources*, not the host.** `summarize` builds
   `summaries/sources/<name>.md` per atlas source. The repo's own `src/` is not
   an atlas source, so the summary spine would cover the *borrow-from* tools, not
   zentaizo itself (which is arguably fine — the code is right there).

## The three decision axes

Everything below is a point in a 3-D space:

- **Axis 1 — where the curated context lives:** *in-repo* (root) vs. a
  *separate external workspace* that vendors zentaizo.
- **Axis 2 — how much machinery we adopt:** *sessions-only* (planning trail) →
  *+ a reference-only atlas* (fetch/summarize the borrow-from tools) → *full*
  (treat zentaizo itself as an editable atlas source).
- **Axis 3 — what is publishable:** the *raw* meta-trail vs. a *curated
  condensation*. The single-editable-repo case forces this axis into the open,
  and it dominates the other two (next section).

### Why the confidentiality axis dominates

In-repo adoption is attractive (one editable repo; design history travels with
the code) — but the raw meta-trail routinely carries **internal discussions,
enterprise agenda, personal correspondence, and other confidential material**.
zentaizo is destined for open-source release (Apache/MIT), and a public git
history is **irreversible**: once a confidential line is committed it is
mirrored, forked, and indexed — scrubbing it later does not un-leak it. So
"commit raw, redact later" is not a safe option; the only safe direction is
**private-first, publish-by-promotion**.

A sharp tension sits underneath: the *negative record* — brainstorming
considered and **not** implemented — is often the single most valuable piece of
design documentation (it tells a future contributor why the obvious path was
rejected) **and** often the most sensitive (it can expose strategy, competitive
analysis, or who-argued-what). The highest-value artifact and the
highest-confidentiality-risk artifact are frequently the same artifact.

The resolution is the **best of both worlds**: keep the **raw trail private** (a
private external workspace as the system of record) and publish a **curated
condensation** — summaries of the meta-analyses, the approaches considered, and
the implementation plans — into the editable repo when desired. Curation is the
**confidentiality filter**, not merely length compression. And condensation is
already a Zentaizo primitive: `summaries/` and the `reports/` charter (living
evidence-backed syntheses) are exactly the right shape, and the unimplemented
"workspace → shareable content export" idea (#5 in
[`ideas-worth-borrowing.md`](2026-05-26-ideas-worth-borrowing.md)) is the same
publish step.

The original framing pointed at **in-repo, sessions + reference atlas**
(Option D). Folding in Axis 3, the safer target for an open-source-destined repo
is **Option E**: a private workspace of record, with curated design-history
published into the repo. D stays viable only for a repo whose trail is
non-sensitive by nature.

## Options (hypotheses)

Per-entry shape mirrors [`ideas-worth-borrowing.md`](2026-05-26-ideas-worth-borrowing.md).

### A. Full in-place workspace (run the repo as a workspace)

- **The idea.** Run the repo *as* a workspace: add `zentaizo.atlas.json`
  listing zentaizo as an `edit` source plus borrow-from tools as `reference`,
  full `sessions/`, `summaries/`, lock, graph. Maximal dogfooding.
- **Maps onto.** Everything in `workspace-format.md`.
- **Why it might help / cost.** Most complete dogfood, but walks straight into
  all four collisions above — especially self-vendoring recursion (#1) and the
  commit-separation break (#2). The repo would not be shaped like a
  `zentaizo create` output, so the tool's own assumptions fight the layout.
- **Status.** candidate (rejected-leaning — highest cost, recursion is ugly).

### B. Separate external workspace (the orthodox model)

- **The idea.** Leave the tool repo untouched. Stand up `~/work/zen-zentaizo`
  via `zentaizo create`; its atlas vendors `repos/zentaizo` as `edit` and the
  borrow-from tools as `reference`. All efforts/sessions/summaries live there,
  in *that* repo's git history. This is exactly the model the commit-trailer
  brainstorm footnote already assumes ("editable-repo work in `repos/zentaizo`
  (→ `~/work/zentaizo`)").
- **Maps onto.** The tool used exactly as designed; zero repo changes.
- **Why it might help / cost.** Purest dogfood of the *real* workflow, no
  collisions, keeps the repo's git history pure code. **But the curated context
  lives outside the repo** — invisible to a fresh clone or an outside
  contributor, not versioned with the code it describes. That defeats the
  stated goal of improving *this repo's* in-place ability to evolve.
- **Status.** candidate (the conservative fallback; sidesteps the ask).

### C. In-repo sessions taxonomy only (no atlas)

- **The idea.** Promote `docs/{brainstorming,changes}` to a full in-repo
  `sessions/` trail: add `efforts.json`, `efforts/`, `debugging/`,
  `questions/`, `handoffs/`, `reports/`, adopt CLI-allocated slice names and the
  `edited_by` ledger. No atlas, no `repos/`, no fetch/summarize/lock — the
  repo's only "source" is its own `src/`, which needs no vendoring.
- **Maps onto.** `sessions/` + the `next-*`/`effort` commands + `zentaizo
  edited`; the CLI's session-file allocation works against any dir with
  `sessions/efforts.json`.
- **Why it might help / cost.** Gets the planning/trail half of the ask cheaply
  and with low migration risk; the `commit-trailer` already works repo-wide.
  **But it drops the atlas/summaries layer** — exactly what "in conjunction with
  ideas-worth-borrowing" wants. C alone is half the ask.
- **Status.** candidate (good foundation; incomplete on its own).

### D. In-repo sessions + a **reference-only** atlas (recommended to explore)

- **The idea.** C, plus an atlas whose `sources.repos` are **only `reference`**
  — the adjacent tools `ideas-worth-borrowing.md` mines (Context Hub, Graphify,
  the Codex/Gemini/Claude-Code harness docs) — and their `docs`. zentaizo
  itself is **not** an atlas source (edited in place, as today), which dodges
  the self-vendoring recursion. `fetch` pins/vendors those reference repos under
  the gitignored `repos/`; `summarize` produces
  `summaries/sources/context-hub.md` etc.
- **Maps onto.** The atlas `role: "reference"` path end-to-end + `sessions/`;
  `repos/` holds only read-only borrow sources, so the sandbox/lock concerns
  shrink to "everything is reference."
- **Why it might help / cost.** This is the synthesis the request points at:
  **`ideas-worth-borrowing.md` graduates from one-time web reads into a pinned,
  summarized, *refreshable* layer.** When Context Hub or Graphify ships a new
  release, `fetch` + `summarize` re-derive the comparison surface and a diff
  shows what changed — the borrow analysis stops going stale. Cost: we adopt
  most of the machinery (atlas, lock, fetch, summarize) for a repo that is
  *not* a normal workspace, so we must document the deviations (no editable
  source; commit rule reinterpreted; summaries cover borrow-sources, not the
  host). Still cleaner than A because nothing is editable under `repos/`.
- **Status.** candidate (strong — directly serves the stated goal; do C's
  groundwork as part of it).

### E. Private workspace of record + curated public design-history (best-of-both)

- **The idea.** The raw meta-trail (full `sessions/`, internal discussion,
  rejected directions) lives in a **private external workspace** (Option B's
  mechanics) that vendors zentaizo as its one `edit` repo. From it,
  **confidentiality-filtered condensations** — design-history notes, approaches
  considered, implementation plans, the brainstorming-not-implemented record —
  are published into the public repo (e.g. under `docs/design/` or as
  `reports/`-style syntheses) **by promotion, never by raw commit**.
- **Maps onto.** B for the private side; `summaries/` / `reports/` + the export
  idea (#5) for the publish step. Reuses D's reference-atlas mapping *inside* the
  private workspace for the ideas-worth-borrowing layer.
- **Why it might help / cost.** Resolves Axis 3: the public repo gains durable,
  travels-with-the-code design documentation **without** leaking confidential
  raw material into an irreversible public history. Cost: two homes to keep in
  sync; the curation/promotion step is manual until (if) export tooling lands;
  and a discipline question — what gets promoted, by whom, at which point in the
  lifecycle.
- **Status.** candidate (strong; the safe default for an open-source-destined
  repo once Axis 3 is in view).

## How concepts would map under D (and the private side of E)

| Workspace concept | In the tool repo (Option D) |
|---|---|
| `zentaizo.atlas.json` | Reference-only sources: the borrow-from tools + their docs. No `edit` repo. |
| `repos/` (gitignored) | Pinned clones of Context Hub, Graphify, harness repos — the comparison corpus. |
| `summaries/sources/*.md` | Distilled, refreshable per-tool summaries feeding `ideas-worth-borrowing.md`. |
| `sessions/efforts/` | The tool's own roadmap (e.g. "summary role-floor", "resurfacing annotations" from the audit). |
| `sessions/brainstorming/` | Where `ideas-worth-borrowing.md` and this doc already live (migrated from `docs/brainstorming/`). |
| `sessions/changes/` | Effort-scoped slices — replaces freeform `docs/changes/` dated design docs. |
| `sessions/reports/` | Living syntheses (e.g. the implemented-vs-unimplemented audit could be a standing report). |
| zentaizo source code | Edited **in place** at the root — *not* an atlas source. |

## The ideas-worth-borrowing payoff (why a reference atlas — under D or E's private side)

`ideas-worth-borrowing.md` is a catalog of ideas from Context Hub and the coding
harnesses, assembled from ad-hoc reading. Under D it becomes the *output* of a
grounded layer: the tools it compares are pinned in the atlas, fetched into
`repos/`, and summarized into `summaries/sources/`. The brainstorm then cites
summaries with provenance instead of memory, and a re-`summarize` after an
upstream release surfaces *new* borrowable ideas as a diff. That closes the loop
the request is reaching for — "used in conjunction with ideas-worth-borrowing" —
in a way C (no atlas at all) cannot. Under E the atlas lives in the private
workspace and only its distilled output is published — the refresh mechanic is
unchanged.

## Migration concerns

- **`docs/changes/` → `sessions/changes/`.** Freeform `YYYY-MM-DD-<slug>.md`
  design docs become effort-scoped `<label>-NNNN-<slug>.md` slices with the
  status schema. Either migrate (rename + reframe under a back-fill effort) or
  keep `docs/changes/` as the historical archive and start `sessions/changes/`
  fresh. Leaning: archive the old, start clean — re-numbering history is noise.
- **`docs/brainstorming/` → `sessions/brainstorming/`.** Lower-friction (same
  `YYYY-MM-DD-<slug>.md` shape, same frontmatter). This very file would move.
- **AGENTS.md reconciliation.** The hand-authored repo guidance must merge with
  the generated `workspace_agents()` conventions without the generated text
  clobbering repo-specific rules (the `upgrade-zentaizo` skill exists precisely
  for this reconciliation — we'd be its first real customer, which is itself a
  useful test). Rewrite the "not a workspace" paragraph to "a workspace of an
  unusual shape: reference-only atlas, host edited in place."
- **`.gitignore`.** A workspace gitignores `repos/`; the repo's `.gitignore`
  would need the same plus the graph local-only entries — without disturbing
  `dist/`, `examples/`, build artifacts.
- **Bootstrapping / version skew.** The repo would run the CLI against itself.
  Which `zentaizo` — the installed one or `pixi run` against the working tree?
  A half-finished CLI change could corrupt the repo's own `sessions/` trail
  (dogfooding hazard). Worth a stated rule (use the released CLI for the repo's
  own session bookkeeping; test working-tree changes against `/tmp` workspaces).
- **`examples/`.** Already holds example workspaces; keep distinct from the
  repo-as-workspace adoption so the two don't blur.

## Open questions

1. **Reference-atlas membership.** Which borrow-from tools earn a pinned source
   (Context Hub, Graphify for sure; the harnesses are docs/websites, not always
   clonable repos — do they enter as `docs` entries with `url`)?
2. **Keep or archive `docs/changes/`?** Re-home into `sessions/changes/` under a
   migration effort, or freeze as `docs/changes-archive/` and start fresh?
3. **Does the commit-separation rule survive at all here**, or become
   "separate commits for `sessions/` vs `src/`"?
4. **Do we want summaries of the host itself** (an effort docs the tool's own
   architecture as a `reports/` synthesis), given `src/` isn't an atlas source?
5. **Is this the moment to run `upgrade-zentaizo` against the repo** as the
   reconciliation mechanism, validating that skill on a real merge?
6. **How much of zentaizo's *own* trail is actually confidential?** If the tool's
   design reasoning is publishable in full, D becomes viable for this repo
   specifically even though E is the safer general default.
7. **Who curates and approves promotion** from private to public, and at which
   lifecycle point (per slice? per effort close? per release)? Without an owner,
   the public design-history silently goes stale or silently over-shares.
8. **Should "single editable repo ⇒ in-repo meta-trail is viable" become a
   documented Zentaizo pattern**, with the confidentiality split as its stated
   caveat — so other single-repo workspaces get the same guidance, not just
   zentaizo?

## Candidate next steps

1. Review this doc; pick a point on the **three** axes (recommendation: **E**
   for the open-source case — private workspace of record + curated public
   design-history; **D** only if the trail is non-sensitive by nature). C's
   groundwork is the first in-repo slice under either.
2. Promote the decision to a dated design doc in `docs/changes/` (the repo's
   current convention) — or, if D is chosen, the *first effort* once
   `sessions/` exists.
3. Slice it: (a) scaffold `sessions/` + `efforts.json` in-repo and migrate
   `docs/brainstorming/`; (b) reconcile AGENTS.md (rewrite the "not a workspace"
   paragraph) and `.gitignore`; (c) author the reference-only atlas and run
   `fetch` + `summarize`; (d) re-ground `ideas-worth-borrowing.md` on the new
   summaries.
4. State the bootstrapping rule (which CLI maintains the repo's own sessions).

## Related

- [`2026-05-26-ideas-worth-borrowing.md`](2026-05-26-ideas-worth-borrowing.md)
  — the borrow catalog this proposal would re-ground on a fetched/summarized
  reference atlas (the "in conjunction with" half of the request).
- `AGENTS.md:11-15` — the "not a workspace" stance this reverses; `:33-34` — the
  existing before/after split that's the partial adoption.
- `docs/workspace-format.md` and `workspace_agents()` (`cli.py:285`) — the
  authoritative conventions being considered for in-repo adoption.
- [`2026-06-15-commit-trailer-command.md`](2026-06-15-commit-trailer-command.md)
  — already assumes the orthodox external-workspace model (Option B) for
  zentaizo's own edits.
