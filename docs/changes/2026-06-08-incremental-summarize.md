---
created: 2026-06-08
status: proposed
edited_by:
  - 2026-06-08  Claude Opus 4.8
  - 2026-06-08  Codex (review)
---

# Incremental, focus-aware `zentaizo summarize`

_Design doc. Drafted 2026-06-08. `zentaizo summarize` today is all-or-nothing: it lists every source and asks the assistant to regenerate every summary, with no memory of which summaries are still accurate. This makes it unusable once a workspace has summaries — adding three repos means re-doing the dozen summaries written an hour ago. This design makes `summarize` **incremental** (pin each summary to the locked state it was made from; only re-do what is new or changed) and **focus-aware** (carry the workspace's intent into the prompt so regenerated summaries don't drift from the framing the original session had)._

_**Revised 2026-06-08 after a Codex review** (findings verified against the code): doc identity is read from the **top-level `lock["doc_snapshots"]`** (where `fetch-docs` actually writes `content_hash`/`status`), not `lock["sources"]["docs"]`; the legacy timestamp fallback is made churn-proof by **preserving `fetched_at` across no-op fetches** (re-stamping only when the resolved identity changed) rather than the unconditional re-stamp fetch does today; **source names gain a slug-safety check** in `validate` because `<name>` is already a path component; and **flagged doc snapshots are routed to a review bucket while reference-only ones are kept-but-annotated**, instead of either silently counting as "current." The four open questions are resolved per Codex below. Status: proposed; Codex signed off 2026-06-08, ready to implement._

A workspace's summaries are the top of its level-of-detail spine — the first thing a future session reads. They are expensive to produce (an assistant reads whole repos and docs) and they go stale silently when a source advances. The current command treats them as disposable: every run is a full regenerate. That is fine for the very first `summarize`, and wrong for every one after it. The fix keys each summary to the snapshot/fetch it was derived from, so the tool can tell *kept-and-current* from *new* from *changed*, and only spends the assistant's effort where it is needed.

## Problem

Two gaps, surfaced while working in `~/work/zen-DSG`:

1. **`summarize` cannot be used incrementally.** It writes one prompt listing *all* sources under a generic "## Sources" heading and asks for `summaries/overview.md`, `summaries/sources/<name>.md`, `relationships.md`, `open-questions.md` — every time, for everything. There is no record of *which locked state* a given summary was made from, so the command cannot distinguish "this summary is still accurate" from "this source changed." Concrete trigger: three repos were just added to the `zen-DSG` atlas with no summaries yet, but the dozen existing `summaries/sources/*.md` were written within the last hour against unchanged sources. Running `summarize` re-solicits all of them. You either redo an hour of work or summarize the newcomers by hand outside the tool.

2. **The prompt carries no workspace focus.** The `zen-DSG` session wrote good summaries partly because it *knew* the work is "DSG integration" and weighted each summary toward what matters for that. The generated prompt contains none of that intent — only per-source `description`s. A future `summarize` (different session, different context window) regenerates summaries that have lost the framing, and consistency between runs degrades. The focus has a durable home (the atlas `description`) and a current-lens home (the active effort's `description`), but the prompt reads neither.

The root cause for (1) is that a summary records no **provenance** — nothing links `summaries/sources/api.md` to the `api` repo commit it summarized. The lock file already records every source's resolved identity (repo `commit`/`head` in `lock["sources"]["repos"]`; doc snapshot `content_hash`/`status`/`fetched_at` in `lock["doc_snapshots"]`); the summary side has no counterpart to compare against.

## The fix: pin each summary to a `source_rev`, then diff against the lock

Give every `summaries/sources/<name>.md` a one-line provenance frontmatter that pins it to the locked identity of the source it was made from:

```
---
source: api
source_rev: 9f3a1c4e7b...        # repo commit/head, or doc content_hash, or "unfetched"
summarized_at: 2026-06-08T18:00:00+00:00
---
# api
…summary prose…
```

On each run, `summarize` reads each summary's `source_rev` (via the existing `read_frontmatter`, `cli.py:2298`) and compares it to the source's current locked identity. Outcomes per source: **new** (no summary file), **changed** (recorded `source_rev` ≠ current locked rev), **current** (match), and — for docs only — **review** (the snapshot is now `flagged`). The emitted prompt asks the assistant to write only the new+changed files, lists current ones as "keep as-is," and surfaces review/flagged docs in their own section. A `--force` flag restores the old behavior (regenerate everything).

This mirrors the lock's own contract — `zentaizo.atlas.json` is human intent, `zentaizo.lock.json` is machine-resolved state, and now a summary's `source_rev` is the machine-checkable claim "I describe *this* resolved state." The single source of truth for "what state was summarized" lives co-located with the summary, the way slice frontmatter lives with the slice.

### Legacy summaries: a timestamp fallback, not a flag day

Every summary in every existing workspace lacks `source_rev` today (including the `zen-DSG` ones written minutes ago). We must not force a one-time full regenerate — that is the exact pain this design removes. So when `source_rev` is **absent**, fall back to a timestamp heuristic that needs no cooperation from past runs:

> If the source was **fetched after** the summary was last written, the summary is probably stale → re-do it. Otherwise keep it.

"When the summary was last written" = the file's git last-commit time (`git log -1 --format=%cI -- <rel>`), falling back to filesystem mtime when the file is untracked/uncommitted. "When the source was fetched" = the source's `fetched_at` in the lock. Any refresh stamps a real `source_rev`, so each summary leaves the fallback path permanently the first time it is touched — the heuristic is **self-retiring**, used once per legacy summary at most.

This works for `zen-DSG`: the recent summaries (written after their repos were fetched) are **kept**; the three new repos have no file → **new**; only they land in the prompt.

**`fetched_at` must not churn (Codex finding).** Today `fetch`/`fetch-docs` stamp `fetched_at = utc_now()` on *every* run (`cli.py:1254/1278/1317/1371`), even when the repo commit or doc content hash is unchanged. Compared against a static summary write-time, an unchanged-but-refetched source would false-stale its legacy summary — reintroducing the churn this design removes. Fix: **preserve the prior `fetched_at` across a no-op fetch.** See "Lock change" below. (`fetched_at` is currently *never read* anywhere in the codebase — verified — so refining its meaning to "when the content we currently hold was obtained" is risk-free; top-level `updated_at` already records "when the lock was last written.")

## Design principles

1. **Reuse the lock as the source-state oracle.** Don't invent a second record of resolved state — the lock already has `commit`/`head` (repos) and `content_hash`/`status`/`fetched_at` (`doc_snapshots`). A summary only stores the one rev it claims to describe.
2. **Definitive check first, heuristic only as fallback.** `source_rev` is exact (content identity). The timestamp comparison is a best-effort bridge for pre-existing summaries and nothing more.
3. **Self-retiring migration, no flag day.** Adopting the feature must not re-solicit existing summaries. The fallback keeps recent work and upgrades provenance lazily on the next genuine change.
4. **The CLI is deterministic; the assistant exercises judgment.** The tool decides *which* sources need work and prints the exact `source_rev` to stamp; the assistant writes prose and transcribes the rev rather than deriving it.
5. **Reuse before adding schema.** `fetched_at` carries the "content last obtained" anchor the fallback needs — no new `rev_changed_at` field (the repo's own "collapse before adding" principle).
6. **Fail safe toward keeping** when neither a rev nor a usable timestamp is available — but never let a security-relevant change (a doc going `flagged`) hide behind "current."

## Classification cascade

Evaluated per source in `summarize_workspace`:

1. `--force` → **todo** (`forced`).
2. Doc whose current snapshot `status == "flagged"` → **review** (never todo/keep; summarizing quarantined content is unsafe, and a previously-ok doc that became flagged is a material change to surface).
3. No `summaries/sources/<name>.md` → **todo** (`new`).
4. Summary has `source_rev`:
   - current locked rev is known and `!=` recorded → **todo** (`changed`);
   - else → **keep** (current).
5. Summary has no `source_rev` (legacy) → timestamp fallback:
   - `summary_time` = git commit time of the file, else fs mtime; if neither is obtainable → **keep** (unverified);
   - source `fetched_at` `>` `summary_time` → **todo** (`changed`);
   - else → **keep** (unverified).

### Locked identity

```python
def _locked_source_index(lock) -> dict[tuple[str, str], dict]:
    # repos/papers/notes from lock["sources"][group];
    # docs from the TOP-LEVEL lock["doc_snapshots"] (where content_hash/status live)
    # -> {(group, name): locked_entry}

def _locked_source_rev(group, entry) -> str | None:
    # repos: entry["head"] or entry["commit"]   (head = what's on disk for edit repos)
    # docs:  entry["content_hash"] if entry["status"] == "ok" else None
    # papers/notes/unfetched/non-ok docs: None
```

`fetch_workspace` writes repo identity to `lock["sources"]["repos"]` (`cli.py:1340`) but only copies atlas docs verbatim to `lock["sources"]["docs"]` (`cli.py:1341`, no hash). Real doc identity is written by `fetch-docs` to `lock["doc_snapshots"]` (`cli.py:1605`). The index must therefore pull docs from `doc_snapshots`, keyed by `name`.

A `None` rev means no fetched content identity to key on. For those, only *missing* is detectable (no false "changed"): a `None`-rev source with an existing summary is **keep** (annotated — see below). A summary for such a source stamps `source_rev: unfetched`; if it later gains a real rev (e.g. a reference-only doc becomes snapshotted ok), `unfetched != <hash>` correctly flips it to **changed**.

### Timestamps

```python
def _git_file_commit_time(workspace, rel) -> datetime | None:
    # guarded subprocess.run (NOT run_git — that raises SystemExit on any non-zero
    # exit, e.g. outside a git repo). Returns None on non-zero exit, empty output,
    # or parse failure. Parses `%cI` with datetime.fromisoformat.

def _summary_written_at(workspace, path) -> datetime | None:
    # git commit time if available, else datetime.fromtimestamp(path.stat().st_mtime, UTC)
```

`utc_now()` (`cli.py:54`) and git `%cI` are both offset-aware ISO 8601, so comparisons parse to aware `datetime`s — never lexical string comparison across timezone offsets. `fetched_at` parses the same way.

## Lock change: preserve `fetched_at` across no-op fetches

`fetched_at` becomes "when the content we currently hold was obtained" (re-stamped only when the resolved identity changes), instead of "the last fetch attempt." Localized to the two workspace-level fetch entry points, leaving `fetch_edit_repo`/`fetch_reference_repo`/`_new_doc_entry` unchanged:

- **`fetch_workspace`** — build the prior index with the existing `_locked_repo_index(old_lock)` (`cli.py:1026`) before the loop. For each freshly locked repo, if `(head or commit)` equals the prior entry's, copy the prior `fetched_at` onto the new entry.
- **`fetch_docs_workspace`** — same pattern against the prior `lock["doc_snapshots"]` keyed by name: if both `content_hash` and `status` are unchanged, copy the prior `fetched_at`.

No prior entry (first fetch, or identity changed) → keep the freshly stamped `utc_now()`. Pre-field locks self-heal on the next fetch.

## Source name safety (Codex finding)

`validate` checks names are *present* (`cli.py:962` repos, `cli.py:974` docs/papers/notes) but not that they are path-safe — yet `<name>` is already a path component (`repos/<name>`, `docs/snapshots/<name>`, `summaries/sources/<name>.md`). A name with `/`, whitespace, a leading dot, or `..` yields ambiguous or unsafe paths and breaks the write-then-`glob`-by-stem round-trip this feature relies on.

Add a global slug check in `validate` for every source group: name must match `^[A-Za-z0-9][A-Za-z0-9._-]*$` (and contain no `..`). All existing atlas names already satisfy this (`shortener-api`, `api-docs`, …). This is a tool-wide correctness fix that this feature surfaces, not summarize-specific.

## The incremental prompt

`summarize_workspace` rewrites `summaries/summarize.prompt.md` as:

- **Workspace focus** (new, top). `name` + atlas `description`; the **current effort** description when meaningful (`load_efforts`/`find_effort`, included only when non-empty and `!= MAIN_EFFORT_DESCRIPTION`, so the default `main` blurb adds no noise); and a `--focus "<text>"` override when passed (highest-priority lens). Guidance: *weight each summary toward this focus, but keep it a faithful general description of the source — don't drop core structure just because it's off-focus.*
- **Summarize these (new or changed)** — `todo` grouped by `repos/docs/papers/notes`, each bullet followed by its `stamp source_rev: <value>` line. A dirty edit repo (`entry["dirty"]`) is annotated: *working tree was dirty when locked; `source_rev` pins the commit only — uncommitted changes aren't captured.* When the section is empty: "everything is current; re-run with `--force`."
- **Keep as-is (do not regenerate)** — the `keep` list. Legacy entries annotated "(no recorded source_rev — staleness unverified)"; reference-only docs annotated "(snapshot reference-only — not refetched; summary may be stale)".
- **Review needed** — docs whose snapshot is `flagged` (quarantined): "snapshot is flagged/quarantined — do not re-summarize from it; review the safety verdict, and any existing summary may describe superseded content."
- **Orphaned summaries** — files in `summaries/sources/` matching no current source. Note only; never auto-delete (a removed-then-readded source, or a rename, shouldn't silently lose prose).
- **Provenance frontmatter** block + trimmed **Guidance** (the old prose "Record provenance" bullet is dropped — provenance is now structured frontmatter).
- Refresh `overview.md` / `relationships.md` / `open-questions.md` only when the source set changed this run (something is under "Summarize these").

Constants: `SUMMARY_REV_KEY = "source_rev"`, `UNFETCHED_REV = "unfetched"`. stdout summarizes the plan: `N source(s) to summarize (a new, b changed); M current[, K need review]`, counted with `collections.Counter`.

## Command surface

On the `summarize` subparser (`cli.py:~3710`):

- `--force` / `--all` (`store_true`) — regenerate every summary, ignoring existing state.
- `--focus TEXT` — per-run framing emphasis. Does **not** mutate the atlas.

## Edge cases and non-goals

- **No lock yet** (created, not fetched). Every locked rev is `None`; missing summaries become `new` with `source_rev: unfetched`. Summarizing before `fetch` works (from atlas descriptions) but can't be staleness-checked until fetched — unchanged from today's order of operations.
- **Edit repo, dirty tree.** `head` advances on commit, not on uncommitted edits, so a dirty-only change to an already-summarized edit repo isn't caught by `source_rev`; it's annotated in the prompt (above) and `--force` is the escape hatch. Dirty state is deliberately *not* folded into `source_rev` — uncommitted content isn't reproducible.
- **Doc went `flagged`** → review bucket (above). **Doc went `reference-only`** (fetch failed / no source) → kept, annotated, since there's no fresh snapshot to summarize.
- **Renamed source.** Old summary becomes an orphan (noted, not deleted); the new name is `new`. Manual reconciliation, by design.
- **Non-goals.** `overview.md` staleness tracking (no single rev — only prompted when the source set changed); auto-deleting orphans; atlas mutation; a `summaries.focus` field; `zentaizo status` coverage reporting (a good follow-on, below).

## Testing

`tests/test_cli.py`:

- Update `test_validate_status_and_summarize_with_atlas`: replace the `"Record provenance"` assertion with `"Provenance frontmatter"` + `"source_rev"`; add a "Workspace focus" assertion.
- `test_summarize_incremental`: atlas with two reference repos + a hand-written `zentaizo.lock.json` (`sources.repos` with commits + `fetched_at`) + one matching `summaries/sources/<a>.md` carrying a `source_rev` equal to the lock commit. Assert `a` under "Keep as-is", `b` under "Summarize these". Bump `a`'s lock commit → `a` becomes "changed". `--force` → both in "Summarize these".
- `test_summarize_docs_via_doc_snapshots`: a `lock["doc_snapshots"]` entry (status `ok`, `content_hash`). Matching `source_rev` → kept; changed `content_hash` → todo; `status: "flagged"` → surfaced under "Review needed", not kept.
- `test_summarize_legacy_timestamp_fallback`: summary with no `source_rev`; source `fetched_at` after the file's mtime → stale (todo); before → kept. (Drive via mtime; git times aren't controllable in a temp dir.)
- `test_fetch_preserves_fetched_at_on_noop`: second fetch with unchanged identity keeps the prior `fetched_at`; a changed commit/hash re-stamps it.
- `test_validate_rejects_unsafe_source_name`: a source named `../evil` or `a/b` fails `validate`.
- `test_summarize_focus`: `--focus "DSG integration"` and a non-default current-effort description both appear under "Workspace focus".

Lint: `pixi run ruff check src/zentaizo/cli.py`.

## Build order

1. **Name safety** in `validate` (independent, smallest).
2. **`fetched_at` preservation** in `fetch_workspace` + `fetch_docs_workspace` (reuses `_locked_repo_index`).
3. Helpers: `_locked_source_index` (docs from `doc_snapshots`), `_locked_source_rev`, `_git_file_commit_time`, `_summary_written_at`; constants; `import collections`.
4. Rewrite `summarize_workspace`: cascade (incl. review bucket) → prompt sections → stdout.
5. `--force`/`--all` and `--focus` on the subparser.
6. Docs: `README.md` (~line 87) and the embedded template README/AGENTS `summarize` step (`cli.py` ~line 241) — note the command is incremental and pins via `source_rev`.
7. Tests above; then full `tests/test_cli.py`.

## Verification beyond unit tests

- Scratch workspace: `zentaizo create /tmp/inc`, author a small atlas, `fetch`, `summarize` (all new), hand-write one summary with a matching `source_rev`, re-run `summarize` (that one kept), re-`fetch` (no-op) and `summarize` again (still kept — proves the `fetched_at` fix), `summarize --force` (all back in todo).
- **zen-DSG A/B (user-driven).** Recent summaries lack `source_rev`, so the fallback keeps them and the prompt lists only the three new repos. To compare run-to-run consistency and focus retention against the original `zen-DSG` session's style, inspect the three newly-generated summaries, or `summarize --force` an already-summarized source and check whether the DSG-integration framing survives. If it doesn't, tune the atlas `description` / `--focus` wording.

## Decisions (resolved 2026-06-08, Codex-reviewed)

- **Staleness key = `source_rev` frontmatter** (content identity), not mtime-vs-`fetched_at` as the primary mechanism. mtime/git is the legacy fallback only.
- **Legacy summaries use the timestamp fallback**, not a one-time full regenerate.
- **Doc identity is read from `lock["doc_snapshots"]`**, not `lock["sources"]["docs"]`.
- **`fetched_at` is preserved across no-op fetches** (reuse the field; no `rev_changed_at`).
- **Source names must be safe slugs** — enforced in `validate`.
- **Flagged/reference-only doc snapshots are surfaced**, not silently "current."
- **Edit repos pin `head`** (what the assistant read); a `dirty` tree gets a warning but is *not* folded into `source_rev`.
- **`--focus` is per-invocation only.** Durable framing → atlas `description`; current framing → active effort `description`. No `summaries.focus` field yet.

## Open questions / follow-ons

1. **`zentaizo status` summary coverage** (current / stale / missing / review counts) so drift is visible without running `summarize`. Out of scope here; natural follow-on.
2. **Orphan reconciliation.** Note-only for now; revisit a `--prune` / rename-aware flow once rename behavior has been exercised.

## Related

- [`2026-06-07-effort-doc-collapse.md`](2026-06-07-effort-doc-collapse.md) — the effort registry + `current` pointer + per-effort `description` this design reads for "current focus."
- [`2026-05-20-api-reference-docs-layer.md`](2026-05-20-api-reference-docs-layer.md) — doc snapshots, `content_hash`, and the safety/quarantine `status` (`ok`/`flagged`/`reference-only`) used as the doc `source_rev` and the review bucket.
- [`2026-05-08-edit-vs-reference-roles.md`](2026-05-08-edit-vs-reference-roles.md) — the role split behind `head`-vs-`commit` for repo identity.
