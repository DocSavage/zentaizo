# Plan and Implement a Change

This procedure helps an LLM-driven coding tool (Claude Code, Codex CLI, Gemini CLI, Aider, etc.) turn a user's change request into a `sessions/changes/` slice plan, execute it across the editable repos in this workspace, and record the outcome. The effort doc in `sessions/efforts/` is the higher-level plan-of-record; slices decompose that effort into executable chunks.

The slice plan file is the single source of truth for one implementation chunk: it captures intent before work starts, tracks progress while it's in flight, and records the actual outcome on completion. The same file lives at the same path the whole way through — do not move or rename it when work completes.

## When to run this procedure

Run it when:

- The user describes a multi-step or cross-repo change they want made.
- The user references a doc in `sessions/brainstorming/` and asks to plan or start work on it.
- The user says "draft a plan", "make a plan", "implement X", "start work on Y".

Do NOT run it for:

- One-line bug fixes that can be made and committed without staging a plan. Describe the change in chat and make it; no plan file needed.
- Open Q&A — use `sessions/questions/` directly.
- Bug investigation that hasn't yet produced a fix-in-scope — run `zentaizo next-debugging <slug>` directly (a debugging note is plan-shaped: a plan for an investigation). If it resolves into a planned change, then run this procedure.

## Pre-flight

Before drafting the plan:

1. Read `AGENTS.md` for workspace rules — especially "Editable vs Reference Repos", "Active Efforts", and "Recording Work in `sessions/`".
2. Read `zentaizo.atlas.json`. List the repos with `role: "edit"`. These are the only repos you may modify in this plan.
3. Identify the **effort** this work belongs to. Run `zentaizo effort list` to see open efforts and which is current. If the work fits an existing effort, `zentaizo effort switch <label>` to it (or pass `--label` per command); if it is a new body of work — possibly spanning several editable repos — start one with `zentaizo effort new <word> --describe "…" --repo <name>=<branch>`, which also scaffolds `sessions/efforts/NNNN-<label>.md` and makes the effort current. Omit `<word>` to get a themed suggestion.
4. If the user pointed at a doc in `sessions/brainstorming/`, read it in full. Otherwise skim recent files there for relevant context — design conversations often contain the constraints the plan needs. If the user gives a new external planning doc or source inventory that may feed this or future efforts, run `zentaizo next-brainstorming <slug>` and paste/summarize it there before slicing.
5. Read `summaries/overview.md` and any source summary covering the components you expect to touch.
6. Read the effort doc with `zentaizo path effort [label]`; it is the plan-of-record above the slices. Then check for related prior slice plans: `zentaizo effort show` lists the current effort's slices, and `zentaizo path active` resolves its active plan. If a related plan is `planned` or `in-progress`, ask whether to extend it rather than start a new one. If a related plan is `done`, read its `## Outcome` for surprises and follow-ups that apply.

## Drafting the plan

1. If the effort doc is still just scaffold text, fill or revise it first and run `zentaizo edited <effort-doc>`. Then run `zentaizo next-change <slug> [--short-title TEXT]` to allocate and scaffold the slice plan in `sessions/changes/`. It composes the name `<label>-NNNN-<slug>.md`, allocates the per-effort counter, and writes the scaffold from `skills/plan-template.md` (see § Session filenames below). Capture the printed path; `zentaizo path slice --next` previews the next id without writing.
2. The CLI has already filled the deterministic frontmatter (`status: planned`; quoted UTC `created`; `label`) and stamped the first `edited_by:` entry crediting whoever ran the command (see § The `edited_by` ledger below). You fill:
   - `short_title`: a discriminator-first title for phone-sized Claude session headers, at most 30 characters. Prefer the subsystem/object/verb that distinguishes this slice from siblings; do not prefix the effort label or add a trailing period. If `--short-title` already filled it, review it rather than assuming it is good.
   - `editable_repos`: only the subset of the effort's `role: "edit"` repos this plan will actually modify.
   - Each repo's branch and divergence base are **not** in the plan — they live in the effort registry. Use `zentaizo effort set-branch <label> --repo <name>` to attach a touched repo before a divergence branch exists, and `zentaizo effort set-branch <label> --repo <name>=<branch>` when you open one (it computes the base sha).
3. Fill in the `## Plan` section:
   - **Problem** — one short paragraph. Cite system context from the atlas/summaries rather than restating it.
   - **Scope** — what's in, what's explicitly out.
   - **Files and components involved** — the parts that move.
   - **Approach** — small, numbered, individually verifiable steps.
   - **Acceptance criteria** — checkable outcomes (one checkbox per criterion). Start criteria unchecked; they are marked complete only during closeout when the outcome supports them.
   - **Verification** — commands, tests, or artifacts that prove each criterion.
   - **Open questions** — anything to confirm with the user before starting.
4. If brainstorming docs informed this plan, link to them by relative path so the lineage is preserved. Generated brainstorming docs have `edited_by:` provenance; raw/freeform dumps may not, and that is allowed.
5. Leave `## Outcome` empty (or omit it) until work is done.
6. Show the user the plan file (or a unified diff) and wait for confirmation before editing any code. Do not start implementation while `status: planned`.

## Reviews

Another agent can review a plan before work starts, or the code before it lands. Fit each review to the use that the plan states.

- **Budget.** Each slice gets one plan review and one code review, unless the effort's "First pass" block sets another budget. A second code review follows only if the fixes change the design.
- **Brief.** Each review brief states the use and the key goals. It asks the reviewer to report over-engineering as well as gaps, and to mark each finding as needed for a key goal or beyond the use.
- **Findings.** Fix the findings that a key goal needs. List the rest for the user as later work, and don't build them.

## Handing off to an implementing agent (planner/implementor split)

If the agent that drafted the plan will also implement it, skip this section and continue to *Executing the plan*.

If a *different* agent will implement (e.g. one model plans, an implementing agent such as Codex, Claude, or Gemini executes):

1. After the user approves the plan (while `status:` is still `planned`), run `zentaizo next-handoff <id> [agent]` — where `<id>` is the paired plan's slice number and the optional `[agent]` topic is `codex`/`claude`/`gemini`/… — to scaffold `sessions/handoffs/<label>-NNNN<letter>[-<agent>].md` from `skills/handoff-template.md`. The handoff is handed to the implementing agent **by reference**, so everything below the frontmatter *is* the prompt: keep it self-contained, cut surrounding narration, and delete the scaffold comment once written. The CLI stamps `created`/`edited_by` (so it's clear which model wrote it) and names the plan as the spec; re-run `zentaizo edited <handoff>` after revising.

   Write the body to name — and *only* what this slice needs (omit what doesn't apply; don't paste standing boilerplate):
   - **Spec** — the plan file is authoritative. Follow it, except where a quoted scope direction in the handoff supersedes it. Stop on any other contradiction.
   - **Scope & guardrails** — which editable repo(s) to change, and the hard "do not touch" boundaries.
   - **Branch state** — the branch, its base, and the expected HEAD, so the implementor doesn't act on stale state.
   - **Inputs / preflight** — required inputs, cached-artifact locations, and the regenerate command when an artifact may be missing.
   - **Verification** — the gates to pass, and what a valid negative/STOP result looks like (a measurement slice can legitimately conclude "no").
   - **Environment quirks** — sandbox/network prefixes, exact branch-creation commands, code-map freshness — *only* when this slice needs them; they are slice-specific, not standing rules.

   Closeout is not re-specified in the handoff: the implementor follows § Closing out below, and commit attribution follows the **implementing** agent's own rule, not the planner's.

   Exception: when the *orchestrating* session (not the implementor) will make the commit — for example, the implementor runs as a delegated subprocess and returns changes for review — follow § Commit attribution below.
2. Hand off. The implementing agent reads `AGENTS.md` + the plan + the handoff, flips the plan to `status: in-progress`, and resumes at *Executing the plan* below.
3. Handoffs are execution glue, not part of the plan's lifecycle: run `zentaizo next-handoff <id> resume` (or `restart`/`diagnosis`) for each restart. It assigns the next per-slice letter, so repeated handoffs never collide (see § Session filenames below).

## Executing the plan

Once the user approves (and, for a split, once the handoff has been written):

1. Confirm the plan frontmatter has a useful `short_title` before execution starts. Fill a blank value, or revise a weak one, then set `status: in-progress` and run `zentaizo edited <plan>` to record your edit in the `edited_by:` ledger (see § The `edited_by` ledger below). Treat the `## Plan` section as frozen from this point, except for marking acceptance criteria checkboxes during closeout. If scope changes mid-flight, capture it as a deviation in the upcoming `## Outcome` rather than rewriting the plan.
2. Work step by step through the approach.
3. Run the verification steps as you go, not just at the end.
4. If a substantive cross-repo question comes up that the user answers, run `zentaizo next-note <slug>` and fill in the Q&A. If a new pre-decision planning input appears, run `zentaizo next-brainstorming <slug>` and keep it cross-effort unless or until an effort consumes it. If a bug investigation is needed mid-implementation, run `zentaizo next-debugging <slug>` — it scaffolds the **same plan shape** as a change (Context / Hypotheses / Investigation / Acceptance criteria / Outcome), so a debugging note is "a plan for an investigation," not a loose trace. Link these back from the plan if they were load-bearing.

### Pausing and resuming

Pause a slice or an effort when it reaches a milestone and more work is planned later.

- **A slice.** Set `status: paused`, and append a `## Paused` section with the date, where the work stopped, and what would resume it. Run `zentaizo edited <plan>`. `zentaizo path active` skips a paused slice. To resume, set `status: in-progress` and run `zentaizo edited` again.
- **An effort.** Run `zentaizo effort pause <label>`. A paused effort takes no new slices or handoffs until `zentaizo effort resume <label>`.

## Closing out

When the work ships (or is abandoned):

1. Append a `## Outcome` section to the same plan file:
   - **What was built** — commits, branches (including any branch switch), key files. Cite SHAs or branch names.
   - **Deviations from the plan** — where reality diverged and why. If a step was skipped, name which acceptance criterion it affects.
   - **Surprises and lessons** — load-bearing context that isn't obvious from the diff.
   - **Follow-up work** — deferred items; link to any new `sessions/changes/` entries you opened.
   - **Links** — PRs, generated artifacts, related debugging or Q&A files.
2. Set the frontmatter to `status: done` (or `abandoned`), and run `zentaizo edited <plan>` to log the closing edit. If this slice finishes its effort, also run `zentaizo effort close <label>`, so the registry shows the effort as closed in later sessions.
3. Review the `### Acceptance criteria` checklist. Mark each fulfilled item as `[x]`; leave unmet or only partially met items as `[ ]` and explain them under **Deviations from the plan** or **Follow-up work**.
4. Show the user the final plan file. Ask whether to commit it alongside the code changes. `AGENTS.md` § Commits gives the commit rules, and § Commit attribution below covers delegated work.

## Reference

### Session filenames

The CLI composes every name below. The shapes are for reading at a glance:

| Directory | Filename | Notes |
|---|---|---|
| `efforts/` | `NNNN-<label>.md` | `NNNN` is the effort's number in the registry. |
| `changes/`, `debugging/` | `<label>-NNNN-<slug>.md` | The two directories share one counter per effort. |
| `handoffs/` | `<label>-NNNN<letter>[-<topic>].md` | `NNNN` is the paired slice's id, and each handoff takes the next letter. Handoffs use no counter. |
| `brainstorming/` | `YYYY-MM-DD-<slug>.md` | Freeform files are also allowed. |
| `questions/` | `YYYY-MM-DD-<slug>.md` | |
| `reports/` | `<slug>.md` | |

- `zentaizo next-change`, `next-debugging` and `next-handoff` work on the current effort. Pass `--label <effort>` to target another. Give `next-handoff` the id `0000` for a handoff that no slice owns.
- `zentaizo next-brainstorming`, `next-note` and `next-report` work across efforts and use no counter. Brainstorming notes and Q&A logs carry a date in their names because they are topical. A report is revised in place, so its name is only its topic.
- The other names carry no date. A file with frontmatter records its creation time in `created:` (ISO 8601 UTC) and each later edit in `edited_by:`.

### The `edited_by` ledger

Each session file with frontmatter carries an `edited_by:` list: effort docs, slice plans, debugging notes, handoffs, reports, and brainstorming notes made with `next-brainstorming`. The list records, in order, who created, reviewed, or changed the file. Each entry is a git-style local timestamp, two spaces, and the editor's identity:

```text
edited_by:
  - Tue Jun 2 12:41:53 2026 -0400  Claude Opus 4.8 (1M context, reasoning xhigh)
  - Thu Jun 4 23:33:15 2026 -0400  Codex gpt-5.5 (reasoning xhigh)
```

- The command that scaffolds a file writes its first entry. `zentaizo edited <path>` adds each later one.
- Consecutive edits by one editor collapse into one entry, whose timestamp moves forward. A different editor adds a new line, so a handoff between models, or to a human, stays visible.
- Let the CLI write every entry, because a model cannot reliably name its own model id. `zentaizo edited` reads the identity from the cache that commit attribution uses, and for Codex it can fall back to the Codex config. In a human shell it records `git config user.name`. `--as "<identity>"` overrides both.
- Session files have no `updated:` field. The latest `edited_by:` entry is the last-modified time, and `created:` stays fixed. At each status change, run `zentaizo edited <path>` to move that time forward.
- A raw dump in `brainstorming/` may have no frontmatter. Add frontmatter before you edit it, or leave the dump as unchanged input.

### Commit attribution

`AGENTS.md` § Commits gives the rule: paste the output of `zentaizo commit-trailer` into each AI-authored commit. The command prints the real model and reasoning effort, works in editable repos that have no hook, and fails loudly when it cannot resolve the identity. The bundled commit-attribution hook is a best-effort backstop where it is installed.

When another agent implemented the change and the orchestrating session commits it, take these steps:

1. When the delegated run returns, run `zentaizo delegation note --codex|--claude --repo <repo>` once for each repo it touched. `--as "<identity>"` overrides the resolved identity. `--repo` names the checkout where the commit will be made. In a linked worktree, pass the worktree's path.
2. At commit time, run `zentaizo commit-trailer --repo <repo>`. It prints one `Co-authored-by:` line for each recorded implementor and a `Reviewed-by:` line for the committing session. Pass `--also-author` when the committing session also wrote code.
3. After the commit lands, run `zentaizo delegation clear --repo <repo>`.

Only `commit-trailer` carries delegated attribution: the hook alone records just the committer. A delegated agent that commits during its own run needs no note, because the hook detects the innermost agent.

## Boundaries — what this procedure does NOT do

- It does not modify `zentaizo.atlas.json`. If a plan reveals the atlas is wrong (a repo's role should change, a new dependency emerged, a description is stale), surface that to the user and suggest running the curate-atlas procedure separately.
- It does not commit code on the user's behalf unless the user explicitly authorizes it.
- It does not rename or move the plan file once created. The same path holds intent and outcome so future sessions can read both.
