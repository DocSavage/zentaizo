---
created: "2026-06-12T15:08:40Z"
edited_by:
  - 2026-06-12  Claude Fable 5
---

Implement the plan at `docs/changes/2026-06-12-graphify-graph-layer.md` as
the authoritative spec. Read it in full before writing any code — it carries
the design rationale, an 8-step build order, a named test plan, and four
resolved questions you must not relitigate. It has been through three Codex
review passes and is signed off; spec base is commit `44135c2` on `main`.

## Repo context

- This is the **Zentaizo tool repo**, not a workspace — no atlas, no
  `sessions/` trail. Conventions live in `AGENTS.md`.
- Trunk-based: commit directly to `main`, at verified milestones, with
  bullet-point commit bodies. A `prepare-commit-msg` hook stamps model
  attribution — do not hand-write a `Co-authored-by` trailer.
- Dev loop: `pixi install`, then `pixi run check` (ruff lint + unittest
  `tests/`). Run focused tests for the changed area before the full check.

## Order of work

**Step 1 of the spec's build order gates everything — do it first and write
the outcomes back into the spec doc before coding.** Install Graphify
(`uv tool install graphifyy` — PyPI name has the double y; CLI is
`graphify`), pin the version you tested, and verify against a scratch
workspace:

1. Where `graphify-out/` lands relative to CWD vs scanned paths; multi-path
   invocation vs ignore-file-only scoping.
2. How the post-commit hook invokes its AST-only rebuild — this decides the
   default (code-only) mode's invocation mechanism.
3. `.graphifyignore` priority/negation at a root whose `.gitignore` hides
   subtrees (the workspace case).
4. Whether an AST-only `--update` on a `--semantic`-built graph preserves
   semantic nodes — gates fetch auto-refresh for `mode: semantic`.
5. Cache shape/size and whether entries embed raw source chunks — finalizes
   the **provisional** commit-`cache/` default (raw `repos/` chunks flip it
   to gitignored).

Amend the spec with these findings (flip provisional defaults as found,
append to its `edited_by:` ledger, add a dated note). If you cannot install
or run `graphify` in this environment, stop after attempting and report —
do not implement against unverified behavior.

Then follow the spec's build order steps 2–8 in order, committing per step
or per coherent group.

## Code anchors (verified at `44135c2`; re-grep if drifted)

- `.gitignore` template: `cli.py:798` (drop `docs/snapshots/`,
  `papers/*.pdf`; add `graphify-out/cost.json`, `docs/snapshots/*.flagged.*`)
- `workspace_agents()`: `cli.py:282`, consultation order at `cli.py:299-307`
  (the new graph bullet goes between summaries and docs)
- `status_workspace`: `cli.py:1134`
- `summarize_workspace`: `cli.py:1953` — the pattern to mirror for
  lock-as-oracle staleness; `UNFETCHED_REV` at `cli.py:1810`
- Quarantine pattern to mirror: `_write_snapshot_or_quarantine`,
  `cli.py:1439`
- Sandbox policy: `compute_policy` (see
  `docs/changes/2026-05-30-sandboxing.md`)

## Guardrails (already decided — see the spec's resolved questions)

- Never wrap Graphify's query surface; never auto-install the binary (fail
  with the exact install commands).
- `--semantic` requires an explicit `--backend`; record
  `semantic_backend`/`semantic_model` in the lock.
- `built_from` is mode-scoped; semantic-only sources go in `not_graphed`
  and never stale a code-only graph.
- Fetch auto-refresh is code-only, best-effort, never fails the fetch;
  skips `mode: semantic` graphs unless step-1 item 4 proved preservation.
- Flagged report → move to `GRAPH_REPORT.flagged.md`, nothing left behind.
- Upstream README lives on the **`v8` default branch**, not `main`:
  `https://raw.githubusercontent.com/safishamsi/graphify/v8/README.md`.

## Done means

- Spec build order complete (or a clearly reported stopping point), with
  tests from the spec's "Test plan" section implemented against a **stub
  `graphify` on PATH** — the real binary is for step 1 only.
- `pixi run check` green.
- Docs updated per build steps 5–6 (`workspace-format.md`, `cli.md`, README
  one-liner) and the spec's `status:` advanced (`proposed` → `partial` or
  `implemented`) with a dated note and ledger entry.
- Commits on `main`.
