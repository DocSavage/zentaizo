# Plan and Implement a Change

This procedure helps an LLM-driven coding tool (Claude Code, Codex CLI, Gemini CLI, Aider, etc.) turn a user's change request into a `sessions/changes/` plan, execute it across the editable repos in this workspace, and record the outcome.

The plan file is the single source of truth: it captures intent before work starts, tracks progress while it's in flight, and records the actual outcome on completion. The same file lives at the same path the whole way through — do not move or rename it when work completes.

## When to run this procedure

Run it when:

- The user describes a multi-step or cross-repo change they want made.
- The user references a doc in `sessions/brainstorming/` and asks to plan or start work on it.
- The user says "draft a plan", "make a plan", "implement X", "start work on Y".

Do NOT run it for:

- One-line bug fixes that can be made and committed without staging a plan. Describe the change in chat and make it; no plan file needed.
- Open Q&A — use `sessions/questions/` directly.
- Bug investigation that hasn't yet produced a fix-in-scope — use `sessions/debugging/` directly. If the debug session resolves into a planned change, then run this procedure.

## Pre-flight

Before drafting the plan:

1. Read `AGENTS.md` for workspace rules — especially "Editable vs Reference Repos", "Active Implementation Branches", and "Recording Work in `sessions/`".
2. Read `zentaizo.atlas.json`. List the repos with `role: "edit"`. These are the only repos you may modify in this plan. Reference repos can be read and cited but never written to.
3. If the user pointed at a doc in `sessions/brainstorming/`, read it in full. Otherwise skim recent files there for relevant context — design conversations often contain the constraints the plan needs.
4. Read `summaries/overview.md` and any source summary covering the components you expect to touch.
5. Check `sessions/changes/` for related prior plans. If a related plan is `planned` or `in-progress`, ask whether to extend it rather than start a new one. If a related plan is `done`, read its `## Outcome` for surprises and follow-ups that apply.

## Drafting the plan

1. Create `sessions/changes/<branch_prefix>-NNNN-<slug>.md` using `skills/plan-template.md` as the scaffold. The full convention is in `AGENTS.md` § Filename Convention — read it before choosing a filename, especially the derivation rule for the branch prefix, the discovery procedure for the next available counter value, and the plan-creation collision check. Example for the first plan on a branch with prefix `featauth`: `featauth-0001-token-rotation.md`.
2. Fill in the frontmatter:
   - `status: planned`
   - `created` and `updated`: the current UTC time as a quoted full ISO 8601 timestamp, for example `"2026-05-13T22:37:00Z"`
   - `editable_repos`: only the subset of `role: "edit"` repos this plan will actually modify
   - `branch_prefix`: the derived prefix that matches the filename. For non-default-branch work, add `implementation_branch:` and `implementation_base:` as shown in the `skills/plan-template.md` scaffold.
3. Fill in the `## Plan` section:
   - **Problem** — one short paragraph. Cite system context from the atlas/summaries rather than restating it.
   - **Scope** — what's in, what's explicitly out.
   - **Files and components involved** — name the parts that move, not the full repo inventory.
   - **Approach** — small, numbered, individually verifiable steps.
   - **Acceptance criteria** — checkable outcomes (one checkbox per criterion). Start criteria unchecked; they are marked complete only during closeout when the outcome supports them.
   - **Verification** — commands, tests, or artifacts that prove each criterion.
   - **Open questions** — anything to confirm with the user before starting.
4. If brainstorming docs informed this plan, link to them by relative path so the lineage is preserved.
5. Leave `## Outcome` empty (or omit it) until work is done.
6. Show the user the plan file (or a unified diff) and wait for confirmation before editing any code. Do not start implementation while `status: planned`.

## Handing off to an implementing agent (planner/implementor split)

If the agent that drafted the plan will also implement it, skip this section and continue to *Executing the plan*.

If a *different* agent will implement (e.g. one model plans, an implementing agent such as Codex, Claude, or Gemini executes):

1. After the user approves the plan (while `status:` is still `planned`), write a paste-ready execution prompt to `sessions/handoffs/<branch_prefix>-NNNN-<agent>.md`, where `<agent>` is the implementing agent (`codex`/`claude`/`gemini`/…). It should name the plan file as the authoritative spec, the editable repos, the environment/preflight steps, and any standing guardrails; keep generated context (commit SHAs, paths, HEAD) current so the implementor doesn't act on stale state.
2. Hand off. The implementing agent reads `AGENTS.md` + the plan + the handoff, flips the plan to `status: in-progress`, and resumes at *Executing the plan* below.
3. Handoffs are execution glue, not part of the plan's lifecycle: write a fresh `-resume`/`-restart` (or `-diagnosis`) variant per restart, and remember they do **not** consume the `changes/`/`debugging/` sequential counter (see `AGENTS.md` § Recording Work in `sessions/`).

## Executing the plan

Once the user approves (and, for a split, once the handoff has been written):

1. Update the plan's frontmatter: `status: in-progress`, refresh `updated` to the current quoted UTC ISO timestamp. Treat the `## Plan` section as frozen from this point, except for marking acceptance criteria checkboxes during closeout. If scope changes mid-flight, capture it as a deviation in the upcoming `## Outcome` rather than rewriting the plan.
2. Work step by step through the approach. Modify files only in repos with `role: "edit"` in the atlas. Read reference repos freely but do not write to them.
3. Run the verification steps as you go, not just at the end.
4. If a substantive cross-repo question comes up that the user answers, save it as `sessions/questions/YYYY-MM-DD-<slug>.md` (questions use the topical date-prefixed convention, not the sequential one). If a bug investigation is needed mid-implementation, save the trace as `sessions/debugging/<branch_prefix>-NNNN-<slug>.md` (debugging uses the same sequential convention as `changes/`). Link these back from the plan if they were load-bearing.

## Closing out

When the work ships (or is abandoned):

1. Append a `## Outcome` section to the same plan file:
   - **What was built** — commits, branches, key files. Cite SHAs or branch names.
   - **Deviations from the plan** — where reality diverged and why. If a step was skipped, name which acceptance criterion it affects.
   - **Surprises and lessons** — load-bearing context that isn't obvious from the diff.
   - **Follow-up work** — deferred items; link to any new `sessions/changes/` entries you opened.
   - **Links** — PRs, generated artifacts, related debugging or Q&A files.
2. Update the frontmatter: `status: done` (or `abandoned`), refresh `updated` to the current quoted UTC ISO timestamp.
3. Review the `### Acceptance criteria` checklist. Mark each fulfilled item as `[x]`; leave unmet or only partially met items as `[ ]` and explain them under **Deviations from the plan** or **Follow-up work**.
4. Show the user the final plan file. Ask whether to commit it alongside the code changes. Workspace plan commits and editable-repo code commits go to different repositories — see `AGENTS.md` § Commits.

## Boundaries — what this procedure does NOT do

- It does not write to Claude Memory, ChatGPT Memory, global Codex memory, or any other assistant-personal store. Project context lives in committed markdown and JSON.
- It does not modify `zentaizo.atlas.json`. If a plan reveals the atlas is wrong (a repo's role should change, a new dependency emerged, a description is stale), surface that to the user and suggest running the curate-atlas procedure separately.
- It does not commit code on the user's behalf unless the user explicitly authorizes it.
- It does not rename or move the plan file once created. The same path holds intent and outcome so future sessions can read both.
