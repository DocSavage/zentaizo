# Plan: Edit vs Reference Repo Roles

## Context

A Zentaizo workspace today treats every repo identically: clone, checkout `ref`, lock the resolved SHA, refresh on `fetch`. That's fine for read-only context but wrong for the workspace's most interesting use case — pulling several related repos into one place to do *coordinated multi-repo edits* with an AI assistant, ideally inside an isolated container so the assistant can be trusted with broad permissions.

Two classes of repos belong in the same workspace:

- **Edit repos** — code we'll modify. We want a known starting commit (so the assistant has an anchored history), but from there we expect the working tree to diverge: branches, dirty files, work in progress. `fetch` must not clobber that work.
- **Reference repos** — code we read but don't change. We want a pin (branch, tag, or SHA). `fetch` should re-resolve and refuse if the working tree is dirty, since dirty here means accidental edits, not work in progress.

Where to enforce the distinction: three layers.

1. **Atlas schema** — declares intent. Source of truth.
2. **CLI behavior** — soft enforcement: `fetch` honors role; `status` flags inconsistencies.
3. **Container/sandbox** — hard enforcement: edit repos mounted RW, reference repos mounted RO. Zentaizo emits a manifest; the user wires it into their sandbox tool of choice.

This plan covers layers 1 and 2 in full and sketches layer 3 as a follow-up so the schema chosen now doesn't paint us into a corner.

## Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Field name | **`role`** per repo entry (short, semantic, no overlap with existing `ref`) |
| 2 | Allowed values | **`"edit"`** and **`"reference"`** |
| 3 | Default when omitted | **`"reference"`** — safer; editing is opt-in |
| 4 | Recorded in lock? | **Yes** — same field, copied from atlas at fetch time. Future `status` and `emit-mounts` read from lock. |
| 5 | Reference repo lock semantics | **Track (always re-resolve).** `fetch` always re-resolves the pin; `ref: main` means "track main"; reproducibility comes from pinning to a SHA or tag explicitly in the atlas. Matches today's behavior. |
| 6 | Edit repo on re-fetch | **Minimal + rebase-aware.** `fetch` does `git fetch --tags --prune` and never touches HEAD. If the working tree is clean and HEAD is behind the freshly-resolved upstream `ref`, `fetch` *prints* the exact rebase command. `zentaizo fetch --rebase` runs the rebase for all clean+behind edit repos. Never auto-rebases without `--rebase`. |
| 7 | Auto-create working branch on first clone? | **No.** Stays neutral; the user (or assistant) decides their branching convention. |
| 8 | Filesystem `chmod` enforcement? | **No.** Breaks `git checkout`, `git gc`, and other internals. Real lockdown belongs in the container layer. |
| 9 | `emit-mounts` command in this plan? | **Deferred** to a follow-up. The schema must support it; the command itself waits until you pick a sandbox tool (devcontainer / docker-compose / podman / dagger / nix). |

## Schema change

A repo entry in `zentaizo.atlas.json` becomes:

```json
{
  "name": "shortener-api",
  "url": "https://github.com/example/shortener-api.git",
  "ref": "main",
  "role": "edit",
  "description": "REST API for creating and resolving short links"
}
```

Semantics by role:

- **`reference`**: `ref` is a pin. `fetch` re-resolves it (so `main` can advance, a tag stays still, a SHA stays still). Lock records the resolved SHA. Dirty working tree blocks `fetch`.
- **`edit`**: `ref` is a *starting point*. On first clone, `fetch` checks it out. On subsequent fetches, `fetch` does not touch the working tree — it only refreshes `git fetch --tags --prune` so the user has remotes available. Lock records the SHA at the most recent successful fetch (which may differ from the user's current HEAD).

`role` is omitted in the existing example file and in the curate-atlas skill template; both fall back to `"reference"`. Existing workspaces continue to work without re-authoring.

## CLI behavior

### `zentaizo fetch [--rebase]`

For each repo, branch on `role`:

```
if role == "reference":
    if dst.exists():
        if working_tree_dirty(dst):
            abort: "{name} (reference) has local changes; refusing to overwrite"
        run_git(["fetch", "--tags", "--prune"], cwd=dst)
        run_git(["checkout", ref], cwd=dst)        # always re-resolve
    else:
        run_git(["clone", url, dst])
        run_git(["checkout", ref], cwd=dst)
    record locked SHA = HEAD, role="reference", dirty=False

if role == "edit":
    if dst.exists():
        run_git(["fetch", "--tags", "--prune"], cwd=dst)
        # do NOT checkout, do NOT touch the working tree
        upstream_sha = run_git(["rev-parse", ref], cwd=dst)   # resolves origin/<ref> via remote
        head_sha     = run_git(["rev-parse", "HEAD"], cwd=dst)
        is_dirty     = working_tree_dirty(dst)
        is_behind    = head_sha != upstream_sha and is_ancestor(head_sha, upstream_sha)

        if is_behind and not is_dirty and args.rebase:
            run_git(["rebase", upstream_sha], cwd=dst)
            head_sha = run_git(["rev-parse", "HEAD"], cwd=dst)
            report: "{name} (edit): rebased onto {ref} ({upstream_sha[:12]})"
        elif is_behind and not is_dirty:
            report: "{name} (edit): behind {ref} by N commits (clean tree)"
            report: "  to advance:  git -C {dst} rebase {upstream_sha}"
            report: "  or run:      zentaizo fetch --rebase"
        else:
            report: "{name} (edit): HEAD={head_sha[:12]} dirty={is_dirty}; upstream {ref}={upstream_sha[:12]}"

        record locked SHA = upstream_sha, role="edit", dirty=is_dirty
        # Note: locked SHA tracks the upstream pin even when HEAD has diverged.
        # The lock answers "what's the canonical version?"; HEAD answers "where is the user?".
    else:
        run_git(["clone", url, dst])
        run_git(["checkout", ref], cwd=dst)
        record locked SHA = HEAD, role="edit", dirty=False
        report: "{name} (edit): cloned and checked out {ref}; create a branch before committing"
```

Two key rules for edit repos on re-fetch:

1. `fetch` never touches HEAD or the working tree. Refresh remotes only.
2. `fetch` reports the rebase command when eligible (clean tree + behind upstream); `--rebase` actually runs it. No interactive prompts — fits headless / scripted use.

The locked SHA for an edit repo records the upstream pin's resolution at fetch time, not the user's HEAD. That keeps the lock semantically consistent across roles ("what does the atlas's `ref` resolve to right now?"), and makes drift visible in `status` (HEAD ≠ locked SHA means the user has diverged, which is the whole point of an edit repo).

### `zentaizo status`

Group output by role and surface useful drift:

```
Workspace: my-system
Atlas: zentaizo.atlas.json
Sources: 4 repos (2 edit, 2 reference), 1 docs, 0 papers, 0 notes

Edit repos:
  shortener-api      branch: feature/expiration   ahead: 3   dirty: yes
  shortener-client   branch: main                 at lock SHA (unchanged)
                                                  upstream main is 4 commits ahead
                                                  -> git -C repos/shortener-client rebase origin/main

Reference repos:
  deployment         pin: v1.4.2                  clean
  shortener-web      pin: main                    DRIFT: HEAD differs from lock SHA  (run `zentaizo fetch` to update)

Lock updated: 2026-04-29T14:02:00+00:00
```

Definitions:

- **Edit repo "at lock SHA (unchanged)"** — current HEAD equals locked upstream SHA. Suggests the user hasn't started edits; not an error. If upstream has advanced past lock, `status` prints the rebase suggestion (mirrors `fetch` output for a quick sync).
- **Reference repo "DRIFT"** — working tree HEAD ≠ locked SHA. Either the upstream pin advanced (run `zentaizo fetch` to update lock) or someone edited the tree (`git -C <path> reset --hard <locked-sha>` to recover).

### `zentaizo validate`

- Accept `role` if present; must be `"edit"` or `"reference"`.
- Treat missing `role` as `"reference"`.
- Reject any other value with a clear error.
- Existing field validation (`name`, `url`, `ref`) is unchanged.

## Lock file shape

Each repo entry gains `role`:

```json
{
  "name": "shortener-api",
  "url": "...",
  "ref": "main",
  "role": "edit",
  "commit": "abc123...",
  "path": "repos/shortener-api",
  "dirty": false,
  "fetched_at": "2026-04-29T14:02:00+00:00"
}
```

Existing locks without `role` are read as `"reference"` for compatibility.

## Curate-atlas skill update

`skills/curate-atlas.md` needs a small addition. Insert a new step after Step 2 ("Central repos") titled **Step 2.5 — Edit or reference?**:

> For each repo, ask: "Will the user edit this repo in this workspace, or read it for context?"
>
> - **Edit**: code that will be modified during this work. The atlas pins a starting `ref` (usually `main`); after the first fetch, the working tree is left alone so the user can branch and commit without `zentaizo fetch` clobbering their progress.
> - **Reference**: code consulted but not changed. The atlas pins a `ref` (branch, tag, or commit); `zentaizo fetch` refuses to overwrite a dirty working tree.
>
> Default to `reference` when in doubt — the user can change it later. A typical multi-repo system has 1–3 edit repos and a longer tail of reference repos (clients, deployment, libraries you depend on).

Also update Step 7 (picking ref values) to cross-reference the role:

> - For `edit` repos: `ref` is the starting point. `main` is usually right; pin to a tag if you need a known-good base.
> - For `reference` repos: pick the strictness you want. `main` for "always current"; a tag for "stable contract"; a SHA for "exact reproducibility".

## Sandbox manifest (sketched, not built here)

A future `zentaizo emit-mounts` command reads the atlas (or lock) and produces a mount manifest in one of several formats. The schema chosen above is sufficient: each entry in the output is `(path, mode)` where `mode = "rw"` for `role: edit` and `mode = "ro"` for `role: reference`. Examples of formats to support later:

- `--format paths` — newline-delimited `<repo-path> <mode>` for shell pipelines.
- `--format compose` — a YAML fragment usable inside a `docker-compose.yml` `volumes:` block.
- `--format devcontainer` — a JSON fragment for `.devcontainer/devcontainer.json` mounts.
- `--format podman` — `--volume <path>:<path>:<mode>` flags.

Build this when you've picked a sandbox tool. The schema chosen now is forward-compatible.

## File-by-file changes (when ready to implement)

### Modified

1. **`src/zentaizo/cli.py`**
   - `validate_workspace`: accept `role`, validate value, default to `"reference"`.
   - `fetch_workspace`: branch on `role` per the pseudocode above; record `role` in each locked repo entry; for edit repos, compute and report rebase eligibility; if `args.rebase`, run the rebase.
   - `build_parser`: add `--rebase` flag to the `fetch` subparser (default off).
   - `status_workspace`: group output by role; flag edit-unchanged-with-rebase-available and reference-drift.
   - `print_counts`: extend "Sources: N repos" to "Sources: N repos (X edit, Y reference)".
   - `default_atlas` (currently unused but kept as a reference seed): annotate at least one repo with `role: "edit"` and one with `role: "reference"` for clarity.
   - `build_reference_block` (used by `provide-info`): unchanged; the role split doesn't affect downstream consumers.

2. **`src/zentaizo/templates/skills/curate-atlas.md`** — insert Step 2.5; update Step 7.

3. **`docs/workspace-format.md`** — extend the `## zentaizo.atlas.json` section with the role field and its semantics; update the JSON example to include both roles.

4. **`docs/cli.md`** — note the new `fetch` and `status` behaviors; brief mention that role is the source of truth for downstream sandbox manifests.

5. **`examples/link-shortener/zentaizo.atlas.json`** — annotate at least one repo as `role: "edit"` to show the convention. Keep the others as `"reference"` (or omit, equivalent).

6. **`README.md`** — one paragraph in "Core Ideas" about edit-vs-reference. The "monorepo for related repos with sandbox-friendly enforcement" framing belongs here; it's the use case that distinguishes Zentaizo from a plain checkout script.

7. **`tests/test_cli.py`** — new tests:
   - `test_validate_accepts_edit_role` — atlas with `role: "edit"`, validate passes.
   - `test_validate_rejects_unknown_role` — `role: "bogus"`, validate fails with a clear message.
   - `test_validate_defaults_to_reference` — repo entry without `role` validates as if `role: "reference"`.
   - Future, requires a fake git repo fixture (probably skip in this iteration unless cheap):
     - `test_fetch_edit_repo_does_not_overwrite_working_tree`
     - `test_fetch_reference_repo_refuses_dirty`

### New

None at the file level. The schema change is purely additive.

## Verification plan

### Unit tests

- Validate accepts `role` field with both values; rejects unknown values; defaults missing values to `"reference"`.
- Status output includes role grouping for an atlas with mixed roles.

### Manual end-to-end (requires real git repos)

1. Create a workspace with two repos: one `role: "edit"` and one `role: "reference"`, both pinned to `main`.
2. `zentaizo fetch` — both clone and check out `main`. Lock records both with their `role`.
3. In the edit repo: `git switch -c feature/x`, make a change, commit. In the reference repo: edit a file but don't commit.
4. `zentaizo fetch` again. Expected:
   - Edit repo: working tree untouched; lock updates the upstream SHA (if `main` advanced); status shows ahead/dirty.
   - Reference repo: aborts with "has local changes; refusing to overwrite".
5. Reset the reference repo (`git checkout .`); re-run fetch. Expected: succeeds, advances to current `main`.
6. `zentaizo status` shows "Edit repos:" / "Reference repos:" sections with the right drift indicators.
7. (Forward-looking) Confirm the lock has enough info to drive a sandbox manifest: each repo has `path`, `role`, and `commit`.

### Backwards compatibility

- An atlas without `role` fields validates and fetches as if every repo were `"reference"` — matches today's behavior.
- A lock without `role` fields is read as `"reference"`; the next fetch upgrades the lock to the new shape.
- Legacy `zentaizo.config.json` workspaces still work (the existing `find_atlas` fallback).

## Open questions

1. **Repo subsets**: `fetch <name>` to fetch only one repo. Useful when you've added a single edit repo and don't want a full re-resolve. Defer; not in this plan's scope.

2. **`.gitignore` for edit repos**: Should we emit a rule so the user doesn't accidentally commit nested `.git/` dirs to *this* workspace? Today `.gitignore` already includes `repos/`, which covers it. No change needed.

3. **Working-branch convention**: The curate-atlas skill stays neutral about branch naming; users have their own conventions. The plan does *not* prescribe `zentaizo/work` or any other prefix.

4. **`fetch --rebase` granularity**: Currently the plan applies `--rebase` to all clean+behind edit repos. If a user wants per-repo control, they can run `git -C <path> rebase` directly (the suggestion is printed). If demand emerges, add `fetch --rebase <name>` later.

5. **Repo move/rename**: If the user changes a repo's `name` in the atlas, the local checkout under `repos/<old-name>/` is orphaned. Out of scope for this plan; would be a `zentaizo prune` follow-up.
