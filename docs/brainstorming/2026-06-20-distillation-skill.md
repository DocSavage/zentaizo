---
created: 2026-06-20
status: brainstorming
edited_by:
  - 2026-06-20  Bill Katz, Claude Opus 4.8 (1M context)
---

# A distillation skill: from noisy zen-workspace provenance to digestible editable-repo design docs

_Brainstorm / idea backlog — hypotheses, not commitments. Follow-on from
[`../changes/2026-06-19-dogfooding-zentaizo-conventions.md`](../changes/2026-06-19-dogfooding-zentaizo-conventions.md),
whose "promotion" step this turns into a concrete capability. Captures the
framing settled in discussion on 2026-06-20: the workspace keeps the full,
low-level provenance; a **user-initiated distillation skill** lifts the
architecture and design motivations into each editable repo's own design docs._

## What this is for (the one driver)

A zen workspace accumulates the **detailed, low-level, often conversational**
record of how a system's design evolved — efforts, change docs, debugging notes,
re-decisions, and (eventually) scanned Slack threads relevant to the work. That
detail is exactly what a future session in the *workspace* wants. It is **not**
what a reader of an *editable repo's* design docs wants.

So the editable repos receive a **distillation**: the current architecture and a
direct account of why it's shaped that way, written to be **digestible and
professional**. The driver is **signal, focus, and readability** — turning noisy
low-level decision-making into clean documentation.

> **This is editorial, not a security control.** Generalizing "who said what,
> when" into author-level decisions ("the authors chose X because Y") is not
> hiding anything — that attribution is *noise* to a repo reader, and abstracting
> it simply reads better. Conversations are not persisted verbatim because they
> are full of side topics and irrelevant detail. Framing this as
> "confidentiality" oversells it; it is common-sense distillation to a
> professional level. (A workspace may still be kept private for ordinary
> project reasons — but that is independent of, and not the point of, this skill.)

## Two principles for a distilled (promoted) design doc

1. **Repo-scoped.** It addresses just that repo's needs, referencing other repos
   only where the dependency is load-bearing. The workspace's full cross-repo
   context stays in the workspace.
2. **Distilled architecture + rationale, generalized.** The current working state
   and a direct "why we arrived here" — not the provenance, not the churn, not
   verbatim discussion. Personal specifics (names, who-said-what, timestamps)
   become author-level statements.

The full provenance and implementation detail remain in the workspace; the
editable repo gets only the distillate.

## The skill: user-initiated distillation

**Working decision: user-initiated, not automatic.** A skilled agent runs on
request, reads the workspace's settled decisions, and proposes/updates the
distilled design docs in the target editable repo(s).

Why user-initiated wins:

- It is the natural **human review gate** — distillation produces docs that
  become part of a (likely public) repo; a person should approve them.
- It lets people **edit the editable-repo docs directly** and have the next run
  *reconcile* rather than race against those edits.
- The trail is **churny and re-decided**; auto-distilling on every change would
  thrash and is exactly when human work gets paved. Distillation is an
  "eventually, once it has settled" activity, which fits a manual trigger.

Cost: editable-repo docs can drift stale between runs. Acceptable by design.

## Non-clobber: preserving human refinement

The core engineering problem is **not paving human work on re-distillation.**
There are two override channels, with different roles:

- **(A) Authoritative workspace alterations.** A human adds a correction to a
  change doc *in the workspace*, clearly marked as a human alteration. This is
  **high-priority input**: later distillations honor it instead of re-deriving
  past it. (Easy — it is just prioritized source material.)
- **(B) Protected editable-repo edits.** A human edits the distilled doc *in the
  editable repo* directly. The distiller must **detect these and avoid paving
  them.** (The hard part — regenerating an output while preserving manual edits
  to it.)

### Prior art already in the repo: `upgrade-zentaizo`

This is the same shape as the existing `upgrade-zentaizo` skill, which reconciles
*tool-template vs. workspace-local edits* — diff, classify each delta, plan, and
**execute on approval**. The distillation skill is its sibling: *workspace
provenance vs. editable-repo-local edits*, a **3-way reconcile** of
(last-distilled / new-distilled / current-with-human-edits) behind an approval
diff. Build it in that shape.

Mechanism sketch (for the open questions below): the distilled doc carries
frontmatter recording **what it was distilled from** (effort/commit) plus an
`edited_by`-style ledger marking distiller-owned vs. human-owned spans, so (B) is
detected by reconcile rather than by vigilance.

## Relationship to the dogfooding design doc

This skill is the **general workspace → editable-repo promotion mechanism** — not
zentaizo-specific. [`../changes/2026-06-19-dogfooding-zentaizo-conventions.md`](../changes/2026-06-19-dogfooding-zentaizo-conventions.md)
adopts it as the promotion mechanism for the zentaizo workspace. As a general
capability it is a candidate bundled skill template (alongside
`plan-and-implement`, `curate-atlas`), so every workspace can distill into its
editable repos.

zentaizo's *initial* `docs/` migration — relocating its pre-existing
`docs/brainstorming/` + `docs/changes/` into the workspace — is a **one-off
bootstrap** (zentaizo has never been under a workspace), handled in the
dogfooding doc. It is **not** part of this skill, which models the ongoing,
typical case.

## Open questions

1. **How are human spans marked/detected in editable-repo docs (channel B)?**
   Frontmatter ledger + last-distilled snapshot diff? Fenced
   `distiller-owned`/`human-owned` regions? Git-blame heuristics? The reconcile
   quality hinges on this.
2. **Granularity.** One distilled doc per editable repo, per architecture area,
   or per effort? How does the distiller decide the doc's boundaries?
3. **"Settled enough."** What signals that a decision has stabilized enough to
   distill (effort close? an explicit mark?) versus still being churned?
4. **Bundled skill vs. workspace-local.** Ship it in
   `src/zentaizo/templates/skills/` for all workspaces, or prototype workspace-local first?
5. **Overlap with `summarize`.** `summaries/sources/*.md` describe *sources*;
   this produces *editable-repo design docs*. Keep them distinct, or can the
   distiller reuse summary machinery?
6. **Slack ingestion (future, out of scope here).** A workspace scanning Slack
   threads is the scenario that makes verbatim-conversation noise acute — noted
   as motivation, not part of this skill's first cut.

## Related

- [`../changes/2026-06-19-dogfooding-zentaizo-conventions.md`](../changes/2026-06-19-dogfooding-zentaizo-conventions.md)
  — parent; its "promotion" step is this skill, and its confidentiality framing
  needs the reframe noted above.
- [`2026-05-26-ideas-worth-borrowing.md`](2026-05-26-ideas-worth-borrowing.md)
  — idea #5 (workspace → shareable content export) is the same "publish distilled
  knowledge" instinct this realizes.
- `upgrade-zentaizo` (bundled global skill) — the existing 3-way
  reconcile-on-approval pattern this skill mirrors.
- `plan-and-implement`, `curate-atlas` (bundled skill templates) — the family
  this would join if shipped tool-wide.
