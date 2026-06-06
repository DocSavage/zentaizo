---
status: planned
created: "YYYY-MM-DDTHH:MM:SSZ"
label: main
editable_repos: []
edited_by:
# related: [<path>, ...]
---

<!--
  CLI-consumed contract: `zentaizo next-change` / `next-debugging` scaffold this
  file by string-replacing the `status`, `created`, and `label` frontmatter
  lines above, and stamping the first `edited_by:` entry. Keep those keys
  present, at the start of their line, and the frontmatter as the very first
  thing in the file (a reader scans the leading `---` … `---` block). There is
  no `updated:` field — run `zentaizo edited <this file>` after each substantive
  edit to extend the `edited_by:` ledger (who crafted, reviewed, or modified the
  plan, and when); the latest entry is the effective last-modified time. Never
  hand-write the model name. The effort's per-repo branch and base sha live in
  the registry (`sessions/efforts.json`), not here.
-->

# <Concise plan title>

Brief one-paragraph framing of what this change is and why now. Link to the brainstorming source(s) it was distilled from, if any (`sessions/brainstorming/<file>.md`).

## Plan

Written before work starts. Treat as frozen once `status` moves to `in-progress`; edit only to correct factual errors.

### Problem

What needs to change and why. One short paragraph. Cite the system context from `zentaizo.atlas.json` rather than restating it.

### Scope

- In scope: ...
- Out of scope: ... (things that look related but are explicitly deferred — helps future sessions resist scope creep)

### Files and components involved

List the editable repos this plan touches (must match `role: "edit"` entries in the atlas) and the key files or surfaces that will change. Do not duplicate the full repo inventory from the atlas; name only the parts that move.

### Approach

1. Step 1 — small, verifiable.
2. Step 2.
3. ...

### Acceptance criteria

- [ ] Specific, checkable outcome.
- [ ] ...

### Verification

How to confirm each acceptance criterion. Build commands, tests to run, artifacts to inspect, metrics to capture.

### Open questions

Anything to confirm with the user before starting.

## Outcome

Appended when `status` moves to `done` or `abandoned`. Until then, leave this section empty or omit it.

### What was built

What actually shipped. Reference the commits or branches, not just descriptions.

### Deviations from the plan

Where the implementation diverged from the plan and why. If a step was skipped, say which acceptance criterion it affects.

### Surprises and lessons

Anything future sessions on this workspace should know — load-bearing context that isn't obvious from the diff.

### Follow-up work

Things deferred or discovered. Link to new `sessions/changes/` entries if substantial.

### Links

Commits, PRs, generated artifacts, related debugging or Q&A sessions.
