---
created: 2026-06-10
status: proposed
edited_by:
  - 2026-06-10 Claude Fable 5 (reasoning xhigh)
---

# Allow documented amendments to `planned` and `in-progress` slice plans

_Design doc. Drafted 2026-06-10 from a real case in the zen-DSG workspace._

## Problem

The plan lifecycle docs treat the `## Plan` section as write-once:

- `templates/skills/plan-template.md`: "Written before work starts. Treat
  as frozen once `status` moves to `in-progress`; edit only to correct
  factual errors."
- `templates/skills/plan-and-implement.md` (executing, step 1): "Treat the
  `## Plan` section as frozen from this point ... If scope changes
  mid-flight, capture it as a deviation in the upcoming `## Outcome`
  rather than rewriting the plan."

Two gaps in practice:

1. **While `status: planned`**, decisions routinely arrive in conversation
   after the plan is drafted but before work starts — the user resolves an
   open question, redirects scope, or adds a requirement. Amending the
   plan is obviously right (it is still pre-work intent), but no skill
   text says so, and the freeze language can read as starting at drafting
   time. Real case (2026-06-10, zen-DSG): `dvid-0005-maxlabel-fixes` was
   amended twice while `planned` — first resolving an open question (admin
   gating for counter-override endpoints), then absorbing an
   admin-consolidation work item at the user's direction. The agent did
   the sensible thing, but the skill neither blessed nor structured it.
2. **While `status: in-progress`**, the only sanctioned record of a
   *user-directed* scope change is a deviation note written at closeout.
   That loses the decision's timestamp and rationale, and it leaves the
   live plan misleading for the rest of the implementation — the document
   everyone is told is the single source of truth no longer describes the
   agreed work. Deviations-at-closeout makes sense for *discovered*
   divergence ("the approach didn't survive contact with the code"), but
   user redirection deserves to update the contract itself.

The freeze exists for a good reason — `## Outcome` deviations are measured
against pre-work intent, and silent in-place rewrites would destroy that
baseline. The fix should preserve the baseline, not abolish the freeze.

## Proposal

Documentation-only change to the bundled skill + template (and any echo in
`cli.py` strings):

1. **While `planned`: the `## Plan` section is freely editable.** State
   this explicitly. Each substantive amendment is logged with
   `zentaizo edited <plan>` as usual; resolved open questions should be
   struck through or annotated with the decision date rather than deleted,
   so the decision trail stays visible.
2. **While `in-progress`: original plan text stays intact; user-directed
   changes go in a dated `### Amendments` subsection** appended under
   `## Plan` (after `### Open questions`). Each entry: date, what changed
   (scope/approach/criteria), and why — typically one short paragraph,
   added when the user redirects mid-flight. Acceptance criteria may be
   added or struck (with annotation) by amendment; existing criterion text
   is never silently rewritten.
3. **Closeout reconciles against plan-plus-amendments**: "Deviations from
   the plan" in `## Outcome` records where implementation diverged from
   the *amended* plan; amendments themselves are not deviations.
4. Keep the existing rules unchanged: no implementation while
   `status: planned`, and discovered (non-directed) divergence still goes
   to `## Outcome` deviations.

## Non-goals

- No CLI changes; amendments are plain markdown, attributed through the
  existing `edited_by` ledger via `zentaizo edited`.
- No amendment mechanism for `## Outcome` (closeout-owned, unchanged) or
  for terminal-status plans.

## Sources

- `templates/skills/plan-template.md`, `templates/skills/plan-and-implement.md`.
- zen-DSG workspace: `sessions/changes/dvid-0005-maxlabel-fixes.md`
  (amended twice while `planned`, 2026-06-10) and
  `sessions/questions/2026-06-10-admintoken-secure-domains.md` (the
  conversation that drove the amendments).
- Companion doc: `2026-06-10-superseded-status-docs.md` (same lifecycle
  section of the skill).
