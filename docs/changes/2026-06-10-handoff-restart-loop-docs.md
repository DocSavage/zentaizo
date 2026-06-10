---
created: 2026-06-10
status: proposed
edited_by:
  - 2026-06-10 Claude Fable 5 (reasoning xhigh)
---

# Document the handoff/restart loop — and decide what the user must know

_Design doc. Drafted 2026-06-10 from a real case in the zen-DSG workspace._

## Problem

Two documentation gaps around the handoff → implement → restart loop:

1. **The README never shows the loop.** Handoffs appear exactly twice in
   `README.md` — a bullet about the `sessions/` trail and a line in the
   directory-layout listing. The workflow walkthrough (restructured in
   `6b39472` around install → walkthrough → effort model) goes from plan
   to implementation without ever showing a handoff being written, a
   fresh session picking it up, or a mid-flight restart producing a
   `resume` handoff. The mechanics exist only in the per-workspace skill
   (`plan-and-implement.md` § Handing off) and the workspace `AGENTS.md`
   table row.
2. **The skill recognizes only one motivation for a handoff.** It frames
   handoffs purely as a planner/implementor *agent split* and literally
   says "If the agent that drafted the plan will also implement it, skip
   this section." In practice there is a second, common motivation:
   **fresh-context implementation by the same agent** — the user wants
   implementation to start in a clean context window (context-budget
   hygiene before a large slice), so the planning session writes a
   handoff *to itself*. Real case (2026-06-10, zen-DSG): the user asked
   for exactly this before implementing `dvid-0005`; the agent wrote
   `sessions/handoffs/dvid-0005a-claude.md`, but a literal reading of the
   skill argued against writing it at all. A third motivation —
   mid-implementation restart (`resume`/`restart`/`diagnosis`) — is
   documented in the skill but invisible to README readers.

## Design consideration: what must the user actually know?

The question to settle before writing the docs: is the handoff/restart
loop something the *user* must understand mechanically, or is the user's
surface just plain English with the agent owning the Zentaizo workflow?

Proposed division of knowledge:

- **The user's interface is English on both ends.** Before: "prepare for
  a restart" / "write yourself a handoff before implementing" / "let's
  start implementation fresh." After: "resume dvid-0005" or just
  "resume." The user should never need to know `next-handoff` flags,
  letter allocation, or file naming.
- **The agent owns the mechanics.** The skill should instruct agents to
  recognize those English triggers and map them to the workflow: run
  `zentaizo next-handoff <id>` (initial, fresh-context) or
  `zentaizo next-handoff <id> resume` (mid-flight), write a
  self-contained prompt per the template, log it with `zentaizo edited`,
  and commit it.
- **One irreducible user responsibility remains: delivering the restart
  signal into the fresh session.** A fresh session has no memory, so the
  user must say *something* that locates the work. Two complementary
  mitigations:
  1. **The outgoing agent ends its turn by handing the user a
     letterless, slice-level restart prompt** (e.g. "Implement the
     handoff for dvid-0005."). The handoff *letter* is agent-side
     bookkeeping — the user should never need to know it, and a
     letter-bearing path in the prompt goes stale the moment a `resume`
     handoff is written. This should be a documented obligation in the
     skill, not folklore — it reduces the user's job to copy/paste of a
     prompt that stays valid across restarts. (The exact file path
     remains a fallback for driving an agent that lacks the workspace
     skill.)
  2. **The signal can be as thin as "implement the handoff"**, because
     the incoming agent can derive the target: the workspace already
     exposes `zentaizo path active` (highest open slice for the current
     effort), and the latest handoff for a slice is the highest letter
     in `sessions/handoffs/<label>-NNNN*`. The slice label in the prompt
     ("for dvid-0005") is only needed to disambiguate when several
     slices are open. Optionally formalize discovery with a small CLI
     addition — `zentaizo path handoff [id]` returning the
     latest-lettered handoff for a slice (default: the active slice) —
     so the skill can describe it as one command instead of a glob.

Conclusion: the loop is agent-mechanics, not user-mechanics — but the
README should still *show* it once, because users deciding whether to
adopt Zentaizo need to see that restarts and context resets are a
designed-for part of the lifecycle, not an improvisation.

## Proposal

1. **README walkthrough addition** (keep it short and example-driven per
   repo style): one subsection showing the loop in dialogue form —
   plan approved → user: "write yourself a handoff and let's implement
   fresh" → agent allocates `handoffs/<label>-NNNNa-….md` and replies
   "on restart, prompt: *Implement the handoff for <label>-NNNN*" →
   fresh session resolves the latest letter itself and implements →
   context grows long mid-flight → user: "prepare for a restart" → agent
   writes `…-NNNNb-resume.md` and replies with the *same* letterless
   prompt → fresh session continues. The user-visible prompt never
   changes across restarts; only the agent-side letter advances. No
   flag-level detail; point to the skill for mechanics.
2. **Skill changes** (`templates/skills/plan-and-implement.md`):
   - Replace "skip this section" with the three named motivations:
     (a) different implementing agent, (b) same agent, fresh context —
     at the user's request or when the planning conversation has grown
     long enough that implementation deserves a clean window,
     (c) mid-implementation restart (`resume`/`restart`/`diagnosis`,
     already documented).
   - Add the English-trigger mapping ("prepare for a restart" and
     variants → the workflow above).
   - Add the outgoing obligation: after writing any handoff, the agent's
     final message gives the user the letterless slice-level restart
     prompt ("Implement the handoff for <label>-NNNN"), stable across
     restarts.
   - Add the incoming behavior: a fresh session given "implement the
     handoff [for <label>-NNNN]" resolves the slice (explicit label, else
     `zentaizo path active`), picks the highest handoff letter for it
     (or `zentaizo path handoff` if added), reads `AGENTS.md` + plan +
     handoff, and continues.
3. **Optional CLI addition**: `zentaizo path handoff [id]` as described
   above. Docs-only proposals 1–2 do not depend on it.

## Non-goals

- No automation of the restart itself (the user still opens the fresh
  session and says something); no attempt to carry conversational state
  outside the committed workspace files.
- No change to handoff file naming, letter allocation, or the rule that
  handoffs don't consume the changes counter.

## Sources

- `README.md` (handoff mentions at the sessions-trail bullet and
  directory layout only).
- `templates/skills/plan-and-implement.md` § Handing off;
  `workspace_agents()` handoffs table row in `src/zentaizo/cli.py`.
- zen-DSG workspace: `sessions/handoffs/dvid-0005a-claude.md` (handoff
  written 2026-06-10 for same-agent fresh-context implementation).
- Companion docs: `2026-06-10-superseded-status-docs.md`,
  `2026-06-10-amend-active-plans.md` (same skill, same docs-only family).
