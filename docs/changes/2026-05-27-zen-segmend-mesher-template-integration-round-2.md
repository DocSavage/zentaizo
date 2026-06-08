---
created: 2026-05-27
status: implemented
implemented: 2026-05-27  # 72b60e3
edited_by:
  - 2026-05-27  Claude Opus 4.7
---

# Integrating `zen-segmend-mesher` workspace conventions back into the templates — Round 2

_Round 2. Integrated 2026-05-27 (UTC). Covers `zen-segmend-mesher` commits `4c20b27` (2026-05-17, the round‑1 upgrade point) → `ae9ee43` (2026-05-26). The round‑1 record is [`zen-segmend-mesher-template-integration.md`](2026-05-17-zen-segmend-mesher-template-integration.md)._

## Context

`zen-segmend-mesher` remains the only live Zentaizo workspace and continues to be the proving ground for the conventions. Round 1 promoted six conventions and renamed `zentaizo update` into the AI‑driven `upgrade-zentaizo` skill; immediately afterward the workspace ran that skill (its `sessions/changes/main-0028-upgrade-zentaizo.md`, commit `4c20b27`) to pull itself onto the round‑1 templates. That commit is the clean cutoff: everything Zentaizo‑convention‑related the workspace has done **since** `4c20b27` is the new divergence this round ports.

The cutoff is exact because `4c20b27` left the workspace's `AGENTS.md` / `skills/plan-and-implement.md` / `skills/plan-template.md` equal to what this repo's generators emit, and upstream has **not** touched those generators since (`f31cfe9..HEAD` changed `cli.py` only for the unrelated docs‑layer / fetch‑docs / discover‑docs work). So the workspace diff applies onto the templates without a three‑way merge — with one already‑present exception noted below.

## What changed in the workspace since the cutoff

Five commits carried the convention work (the rest of the ~80 commits since `4c20b27` are mesher domain work — plans, handoffs, render assets — not Zentaizo conventions):

| Workspace commit | Change |
|---|---|
| `63b1dac` | Split `handoffs/` + `reports/` out of `brainstorming/` (retroactively migrated 24 handoff files) |
| `c7dee05` | Added the at‑a‑glance `sessions/` taxonomy table + the before/after/glue mental model |
| `b381ba5` | Made the handoff role convention agent‑agnostic (not Codex‑only) |
| `84e6bb4` | Folded the taxonomy table + mental model into `AGENTS.md` |
| `9d9cb30` | Trimmed the status‑frontmatter block out of `AGENTS.md` (it now lives in the skill/template); added the planner/implementor handoff step |
| `b0c40c8` | Applied a Codex review of the taxonomy wording |

The workspace's own `sessions/changes/main-0029-sessions-handoffs-reports-taxonomy.md` carries an explicit **"Transfer to zentaizo (transfer-ready — lift this into the skill)"** section that is the spec for this round; it stated up front it was **not** yet upstreamed. This document records that it now is.

## The promoted changes

All landed in this repo's generators/templates.

| # | Change | Where it landed |
|---|---|---|
| 1 | Two new `sessions/` subdirectories — `handoffs/` (paste‑ready execution prompts for whichever agent implements) and `reports/` (living, evidence‑backed syntheses with a conclusion) | `workspace_agents()`, `create_workspace()` dir list, README layout tree |
| 2 | At‑a‑glance `sessions/` taxonomy table + the "`brainstorming/` is *before*, `reports/` is *after*, `handoffs/` is *execution glue*" mental model | `workspace_agents()` |
| 3 | `handoffs/` filename convention `<branch_prefix>-NNNN-<role>.md` (slice‑keyed, no date; topical‑slug fallback) and `reports/` `<slug>.md` (topical, living) — added to the filename table | `workspace_agents()` |
| 4 | Sequential counter clarified: **only** `changes/` + `debugging/` consume it; a handoff reuses its paired plan's slice id | `workspace_agents()` |
| 5 | Tightened `brainstorming/` charter to "input *before* a decision" — explicitly **not** execution prompts or finished syntheses | `workspace_agents()` |
| 6 | Status‑frontmatter schema moved out of `AGENTS.md` into the skill + template (dedup); `AGENTS.md` now points at them | `workspace_agents()`, `skills/plan-and-implement.md` |
| 7 | Planner/implementor split: a "Handing off to an implementing agent" section in the skill + a step 4 in `AGENTS.md` § From Brainstorming to Plan | `workspace_agents()`, `skills/plan-and-implement.md` |
| 8 | `upgrade-zentaizo.md` updated: "four `sessions/` subdirectory shells" → six | `templates/global-skills/zentaizo/upgrade-zentaizo.md` |

Generalization edits applied while promoting (consistent with round 1's principle of keeping mesher specifics out of the templates):

- The handoff/report **examples** were degenericized: mesher slice ids (`mcgpu-0041-codex.md`, `multires-meshing-strategies.md`, `compression-research-restart.md`, `current_as_of: mcgpu-0040 (2026-05-25)`) became generic ones (`featauth-0007-codex.md`, `auth-rollout-findings.md`, `auth-migration-restart.md`, `featauth-0007 (2026-05-20)`).
- Where the workspace simply **deleted** the status‑frontmatter block from `AGENTS.md`, the template instead leaves a one‑line pointer to `skills/plan-and-implement.md` + `skills/plan-template.md`. The generated `AGENTS.md` is read standalone (without the workspace's surrounding context), so a breadcrumb to where the schema went is worth the line. Same intent (the skill/template own the schema), slightly more legible in a fresh workspace.

## Fixes folded in

- **Stale `YYYY-MM-DD` session filenames in the generated README.** Round 1 moved `changes/`/`debugging/` to the sequential `<branch_prefix>-NNNN-<slug>.md` convention but never updated the README's steps 5–6, which still showed `sessions/changes/YYYY-MM-DD-<slug>.md` and `sessions/debugging/YYYY-MM-DD-<slug>.md`. Corrected to the sequential convention, and step 6 now also names `handoffs/` and `reports/`. (The same staleness sits in the workspace's older README — see the workspace recommendation below.)
- **Round‑1 doc had no date header** (the original ask that prompted this audit). Added one to the round‑1 doc and cross‑linked the two rounds.

## What was deliberately NOT promoted

- **The consultation‑order swap (`docs/` before `repos/`).** The workspace reordered these in this window, but upstream already made the same change independently (commit `d4c0471`, "Reorder source consultation and add summarize provenance"). No action — the template is already correct, and a test asserts the ordering.
- **`zentaizo.atlas.json` changes.** The workspace's 52‑line atlas diff adds source entries using existing schema keys (`name`/`url`/`role`/`ref`/`path`/`description`) — project content, not a schema or convention change.
- **Mesher domain work** — the ~70 `mcgpu-*` plans, handoffs, debugging notes, and render assets added since the cutoff are workspace artifacts, not conventions.

## Considered but deferred: deterministic CLI helpers for counters/filenames

The original request flagged a recurring dogfooding idea: *replace the AI‑procedure instructions for "find the next slice counter" and "compute the proper session filename" with a small deterministic `zentaizo` subcommand.* Today `AGENTS.md` § Filename Convention encodes this as prose the agent executes — the `derive_prefix` rule, the "Finding the next counter value" shell snippet, and the plan‑creation collision check.

**This idea was not found recorded as a dedicated note in the workspace** (searched `sessions/`, `README.md`, and `docs/design/ideas-worth-borrowing.md`). It surfaced only in passing in `main-0009-zentaizo-workspace-improvements.md`'s scope line "Add CLI support only where the workflow needs durable machine behavior rather than assistant‑side convention." Capturing it here so it is not lost again.

The shape it would take — and why it is deferred, not done:

- A read‑only `zentaizo next-slice [--dir changes|debugging]` that derives the branch prefix, scans `changes/` + `debugging/` for the current prefix, runs the cross‑branch collision check, and prints the next canonical filename (`<branch_prefix>-NNNN-<slug>` skeleton). It fits the repo's thin‑CLI rule (no network, no judgment — just locate‑and‑print) and removes a class of agent arithmetic mistakes (skipped/duplicated counters, wrong zero‑padding, prefix derivation drift).
- It overlaps with idea #4 in [`ideas-worth-borrowing.md`](../brainstorming/2026-05-26-ideas-worth-borrowing.md) ("an explicit agent‑facing retrieval verb"), which proposes a `zentaizo get`/`search` read surface; a counter/filename helper is the same "thin verb the agent calls instead of filesystem spelunking" instinct and shares an output convention with it.

**Now designed:** the full proposal — a `zentaizo next-slice` family that scaffolds the file with deterministic frontmatter across all six session kinds, plus the resulting `AGENTS.md` slimming — lives in [`next-slice-cli-helper.md`](2026-05-27-next-slice-cli-helper.md). The maintainer's steer was explicit: a deterministic tool is preferred over expanding `AGENTS.md` with rules an LLM re‑derives non‑deterministically each session (context rot).

## Recommended next step for `zen-segmend-mesher`

This round was a workspace→template promotion, so the workspace needs **no immediate change from it** — it already carries the taxonomy (it is the source), and its `sessions/handoffs/`+`reports/` directories already exist and are populated.

What the workspace *is* now behind on is the **other** upstream evolution since its last upgrade (`main-0028`, 2026‑05‑17): the `docs/` API‑reference layer, `fetch-docs`/`discover-docs`, the README layout tree, and the untrusted‑source safety posture. Pulling those in is a separate `upgrade-zentaizo` pass run **in the workspace**, and it is genuinely bidirectional — the workspace is *ahead* on the `sessions/` taxonomy and *behind* on the docs layer — so a blind template overwrite would clobber the taxonomy. That pass should:

- Adopt the upstream docs‑layer additions and README layout tree, **preserving** the workspace's `sessions/` taxonomy (now identical to upstream anyway) and its deliberate local deltas (committed‑PDF `.gitignore` policy, project‑specific branch examples, Codex commit guidance).
- Fix the same stale `YYYY-MM-DD` README session paths noted above when the README is refreshed.

It is left as a follow‑up rather than done here because it is an in‑workspace operation the `upgrade-zentaizo` skill is built for, not a change to this template repo.

## Files changed in this integration

- `src/zentaizo/cli.py` — `workspace_agents()`: "Recording Work in `sessions/`" rewritten (four → six subdirs, taxonomy table, mental model, `handoffs/`+`reports/` charters); filename table gains `handoffs/`+`reports/` rows; `NNNN` counter sentence clarified; status‑frontmatter block replaced with a pointer; new step 4 under "From Brainstorming to Plan". `workspace_readme()`: layout tree gains `handoffs/`+`reports/`; stale `YYYY-MM-DD` session paths corrected. `create_workspace()`: dir list gains `sessions/handoffs` + `sessions/reports`.
- `src/zentaizo/templates/skills/plan-and-implement.md` — new "Handing off to an implementing agent (planner/implementor split)" section; the optional‑fields cross‑reference now points at `plan-template.md` (since `AGENTS.md` no longer carries the schema); "Once the user approves" gains the split caveat.
- `src/zentaizo/templates/global-skills/zentaizo/upgrade-zentaizo.md` — "four" → "six" `sessions/` subdirectory shells.
- `tests/test_cli.py` — assert `handoffs/`+`reports/` appear in the generated `AGENTS.md` and README; assert both new directories are created; replaced the `status: planned`‑in‑AGENTS.md assertion with a check for the status‑frontmatter pointer.
- `docs/design/zen-segmend-mesher-template-integration.md` — added the missing date header + round‑2 cross‑link.
- `docs/design/zen-segmend-mesher-template-integration-round-2.md` — this document.
