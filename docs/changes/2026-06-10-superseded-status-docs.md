---
created: 2026-06-10
status: proposed
edited_by:
  - 2026-06-10 Claude Fable 5 (reasoning xhigh)
---

# Document `superseded` as a recognized terminal slice status

_Design doc. Drafted 2026-06-10 from a real case in the zen-DSG workspace._

## Problem

The CLI already treats `superseded` as a closed slice status —
`CLOSED_SLICE_STATUSES = {"done", "superseded", "abandoned"}`
(`src/zentaizo/cli.py`, used by `path active` and short-title checks) — but
none of the documentation an agent actually reads mentions it:

- `templates/skills/plan-and-implement.md` closeout says
  "Set the frontmatter to `status: done` (or `abandoned`)".
- `templates/skills/plan-template.md` Outcome section says
  "Appended when `status` moves to `done` or `abandoned`".
- The `workspace_agents()` string and the global skill text in `cli.py`
  describe the lifecycle as `planned → in-progress → done`.

So an agent following the docs literally must squeeze "this plan was
replaced by a better plan" into `abandoned`, which loses the distinction
between *work we decided not to do* and *work that continues under a
successor plan*.

Real case (2026-06-10, zen-DSG workspace): slice `dvid-0001-maxlabel-bugs`
(a March bug analysis whose fix list a re-review found insufficient) was
replaced by `dvid-0005-maxlabel-fixes`. The user asked for the old slice to
be "marked superseded"; the agent set `status: superseded` and the CLI
handled it correctly everywhere (`effort show` displayed
`dvid-0001 (superseded, changes)`), but only because the agent guessed and
tested — the skill gave no license for it.

## Proposal

Documentation-only change; no CLI behavior change needed.

1. **Define the status** in `templates/skills/plan-and-implement.md`
   (closeout section): `superseded` = closed without (or with partial)
   implementation because a successor plan replaces it. Requirements:
   - the superseded plan gets an `## Outcome` whose body names the
     successor and records *why* the original plan was replaced;
   - the successor plan lists the superseded plan in its `related:`
     frontmatter (lineage in both directions);
   - acceptance criteria in the superseded plan stay unchecked.
2. **Update the template**: `templates/skills/plan-template.md` Outcome
   line becomes "Appended when `status` moves to `done`, `superseded`, or
   `abandoned`."
3. **Update the embedded strings in `cli.py`** (`workspace_agents()` and
   the global-skill lifecycle sentence) to name the full terminal set, e.g.
   `planned → in-progress → done/superseded/abandoned`.
4. Existing workspaces pick the wording up through the normal
   `upgrade-zentaizo` reconciliation path.

## Non-goals

- No CLI validation or enforcement of status values (statuses remain
  free-form strings; `CLOSED_SLICE_STATUSES` membership is the only
  behavior, and it already includes `superseded`).
- No automatic back-link tooling between predecessor and successor; the
  skill text just instructs agents to write both links.

## Sources

- `src/zentaizo/cli.py` — `CLOSED_SLICE_STATUSES`.
- `templates/skills/plan-and-implement.md`, `templates/skills/plan-template.md`.
- zen-DSG workspace: `sessions/changes/dvid-0001-maxlabel-bugs.md` (superseded)
  and `sessions/changes/dvid-0005-maxlabel-fixes.md` (successor).
