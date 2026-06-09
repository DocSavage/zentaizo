---
created: 2026-06-08
status: brainstorming
edited_by:
  - 2026-06-08  Claude Opus 4.8 (1M context)
---

# Focused summaries that still describe the source: a "role floor" + retrieval hints

_Brainstorm / idea backlog — hypotheses, not commitments. Direct follow-on to
[`2026-06-08-incremental-summarize.md`](../changes/2026-06-08-incremental-summarize.md),
which added the `## Workspace focus` section to the summarize prompt and explicitly
invited a run-to-run consistency check ("If the DSG-integration framing doesn't
survive, tune the atlas `description` / `--focus`", §Verification). This note reports
what that check found in `~/work/zen-DSG` and proposes the next iteration of the
focus mechanism._

## What prompted this

The incremental-summarize feature regenerates only new/changed source summaries and
carries the workspace's intent into the prompt via `## Workspace focus`
(`_summarize_focus_lines`, `cli.py:1918`) plus one soft guidance line:

> "Weight each summary toward this focus, but keep it a faithful general description
> of the source — don't drop core structure just because it's off-focus."
> (`cli.py:2072-2073`)

I ran the invited experiment: in zen-DSG, regenerate two already-baselined source
summaries (`neuPrintHTTP`, an `edit` repo; `PyChunkedGraph`, a `reference` CAVE
service) **from the same locked commit** as their committed baselines, then diff.
Same source state ⇒ every delta is summarizer variance.

## Findings

1. **The high-level focus framing survived — good.** Both regenerations stayed
   auth-weighted (DSG token flow, `/api/v1/user/cache`, `permissions_v2`, TOS gating),
   matching the baseline's emphasis. The `## Workspace focus` section does its job at
   the framing level.

2. **The soft "keep faithful general description" line is too weak — the user-visible
   failure.** One regeneration trimmed *so hard* toward focus that it declared the
   source's core purpose out of scope ("the graph algorithm itself is out of scope
   here"). The baseline had opened with what PyChunkedGraph actually *is* — a
   hierarchical agglomeration graph for real-time proofreading. A downstream agent
   handed the trimmed version learns the auth surface but loses the one paragraph that
   says *what it is and why it exists*. Over-focus obliterated the role, which is
   exactly what the soft line was meant to prevent and didn't.

3. **The dominant variance source was retrieval method, not framing or model
   nondeterminism.** The biggest content deltas traced to *how each run gathered
   evidence*, not how it framed it:
   - The baseline read files directly **and consulted an in-repo doc**
     (`repos/neuPrintHTTP/docs/auth-integration.md`); from it, it knew the outstanding
     DSG-side migration item and the "what was removed in the migration" narrative.
   - The second run fanned out to read-only sub-agents that returned precise,
     line-cited facts but **never opened that in-repo doc** — so it lost the migration
     narrative, the dependency version pin (`middle-auth-client==3.16.1`), and the
     route-by-route permission breakdown, while *gaining* line numbers and one route
     the baseline had missed.

   Net: the second run was better-cited but less complete and less actionable. The
   prompt's "reuse docs, don't regenerate" guidance (`cli.py:2148`) is necessary but
   not sufficient — nothing **named which in-repo docs to consult for a given source**,
   so whether they got read was left to chance.

## The problem, sharpened: summaries serve two agents

Summaries are the top of the level-of-detail spine — the first thing a future,
context-free session reads. Two distinct consumers have unmet needs:

- **The writing agent** needs the focus lens *and* a hard floor: it must never trim
  away the general role, however off-focus. Today only a soft aside protects that.
- **The reading (downstream) agent** needs to know *which lens the summary was written
  through*, so it doesn't over-trust intentionally thin off-focus coverage. Today the
  summary carries no record that it is, say, "DSG-auth-weighted" — a consumer can't
  tell a deliberately shallow section from a complete one.

## Ideas (hypotheses)

Per-entry shape mirrors `2026-05-26-ideas-worth-borrowing.md`.

### A. A non-negotiable "role floor" in the summary contract

- **The idea.** Promote the soft line (`cli.py:2072-2073`) to a *structural*
  requirement in the Output-Files contract: every `summaries/sources/<name>.md` opens
  with a short, **focus-independent** block — what the source is and its role in *its
  own* ecosystem, ~2–4 lines, written as if the workspace focus did not exist — and
  *then* the focus-weighted depth. "Floor, then focus."
- **Maps onto.** Prompt text only: the `## Output Files` block (`cli.py:2075`) and the
  guidance line. Optionally a one-line skeleton the agent fills.
- **Why it might help / cost.** Directly fixes finding #2 and is the user's explicit
  ask ("without it completely obliterating at least a few lines generally describing a
  repo's role"). Near-zero cost (prompt wording). Risk: a rigid skeleton fighting a
  genuinely unusual source — keep it a *minimum*, not a fixed template.
- **Status.** candidate (strong; smallest change, highest user-visible payoff).

### B. Record the lens in the summary's provenance

- **The idea.** Stamp the focus actually used into the provenance frontmatter the
  prompt already requires (`cli.py:2130`), e.g. a `focus:` line alongside
  `source`/`source_rev`/`summarized_at`. A downstream agent then knows "this is
  auth-weighted; off-focus sections are deliberately thin — drop to `repos/` for the
  rest."
- **Maps onto.** The existing provenance block — one added line, no new file or schema
  elsewhere. (Distinct from the design doc's *non-goal* of a durable `summaries.focus`
  **atlas** field — this is per-summary provenance recording what lens *was* applied,
  not a new configuration knob.)
- **Why it might help / cost.** Serves the second consumer (the reader) cheaply; makes
  the focus auditable across runs. Cost: another field to transcribe; only worth it if
  consumers are taught to read it (pairs with `AGENTS.md` consultation order).
- **Status.** candidate.

### C. Per-source retrieval hints (the biggest consistency lever)

- **The idea.** Under "Summarize these," list — per source — the in-repo docs/specs to
  consult *before* summarizing it. The atlas already links docs to repos via the
  `docs[].repo` field, so the prompt can derive, for each repo, the atlas `docs`
  entries whose `repo == <name>`; plus a light scan for the repo's own
  `docs/`/`README`/`*.md` worth flagging. This is what would have closed the gap in
  finding #3 — the baseline's edge came entirely from reading
  `docs/auth-integration.md`, and nothing told the second run it existed.
- **Maps onto.** `summarize_workspace` todo-bullet rendering + a new derivation step;
  reuses `docs[].repo` (api-reference-docs-layer) and `source_groups`.
- **Why it might help / cost.** Highest leverage on run-to-run consistency — it
  attacks the *dominant* variance source, not a secondary one. Cost: real code
  (per-source doc enumeration, a scan heuristic) and the risk of noisy hints on
  doc-heavy repos. Could ship the cheap half first (just surface atlas `docs` whose
  `repo` matches) before any filesystem scan.
- **Status.** candidate (highest leverage; do A first, then this).

### D. Role-aware closing section

- **The idea.** `role` + focus imply the right *ending* for a summary. A `reference`
  repo whose purpose is compatibility validation should close with an actionable
  contract/checklist ("what the replacement must satisfy"); an `edit` repo should close
  with "integration status / what's left." The baseline did this unprompted; the second
  run didn't, because nothing asked for it. The prompt could emit a per-`role`
  structural hint.
- **Maps onto.** The `role` field (edit-vs-reference-roles) + prompt text; the focus
  string tells the agent *what kind* of contract matters.
- **Why it might help / cost.** Recovers the actionability the second run lost; makes
  reference-repo summaries pull their weight (they exist to be validated against). Cost:
  modest prompt wording; risk of formulaic endings if over-specified.
- **Status.** candidate.

## Why this matters

Summaries are expensive to produce and are read first, by a session with no other
context. The two regressions observed — obliterating the general role, and
method-dependent completeness — both bite hardest exactly when the summary is handed
to a fresh agent. A floor (A) guarantees orientation; lens-recording (B) tells the
reader how far to trust it; retrieval hints (C) make the *content* reproducible
regardless of how the writing agent gathers evidence; role-aware endings (D) make each
summary do the job its role implies.

## Open questions

1. **How big is the floor (A)?** A hard line count, or "enough that a reader unfamiliar
   with the source could place it"? Probably the latter, stated as a minimum.
2. **Does the lens belong in frontmatter (B) or prose?** Frontmatter is machine-
   checkable and matches the provenance pattern; prose is lower-ceremony. Leaning
   frontmatter.
3. **Retrieval hints (C): prompt-time list vs. a real retrieval verb.** Overlaps with
   idea #4 in `2026-05-26-ideas-worth-borrowing.md` (an agent-facing
   `zentaizo get <source>`). If that verb lands, "consult these docs first" could route
   through it instead of an inline list.
4. **Should any of this become an `AGENTS.md` consultation-order rule** for the
   *reading* side, so the lens (B) and floor (A) are actually used downstream?

## Related

- [`2026-06-08-incremental-summarize.md`](../changes/2026-06-08-incremental-summarize.md)
  — parent: added `## Workspace focus`, the soft "keep faithful general description"
  line this note proposes to harden, and invited this consistency check.
- [`2026-05-20-api-reference-docs-layer.md`](../changes/2026-05-20-api-reference-docs-layer.md)
  — the `docs[].repo` linkage idea C derives retrieval hints from, and the
  treat-docs-as-untrusted posture any hint must respect.
- [`2026-05-08-edit-vs-reference-roles.md`](../changes/2026-05-08-edit-vs-reference-roles.md)
  — the `role` split idea D keys its closing-section choice on.
- [`2026-05-26-ideas-worth-borrowing.md`](2026-05-26-ideas-worth-borrowing.md) — idea
  #4 (agent-facing retrieval verb) overlaps with idea C's delivery.
