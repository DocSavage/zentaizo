# Deterministic session paths: `zentaizo path` (resolve) and `zentaizo next-*` (create)

_Design doc. Drafted 2026-05-27; revised 2026-05-27 after a Codex review (pinned the `--prefix`/`--branch`/default-branch and `implementation_branch` rules, `path active` ordering, slice-id form/ambiguity, slug normalization; fixed the `upgrade-zentaizo.md` packaging omission in `pyproject.toml`). Status: proposed (not yet implemented)._

A thin, deterministic CLI for the two things the agent does with session filenames: **resolve** an existing one to read it, and **allocate + scaffold** a new one — replacing the prose procedures in `AGENTS.md` and `skills/plan-and-implement.md` that an LLM re-derives (non-deterministically, with context rot) each session.

## Problem

Allocating a session filename is currently a **procedure the AI executes from prose**. `AGENTS.md` § Filename Convention tells the agent to: derive an 8-char branch prefix with a specific lowercase/strip/truncate rule, run a shell snippet to find the highest existing counter for that prefix, add one, zero-pad to four digits, run a cross-branch collision check by reading other files' frontmatter, then hand-write the new file with `status: planned`, a correctly-formatted UTC ISO timestamp, and the prefix echoed into frontmatter.

Every one of those steps is **deterministic** — there is exactly one correct answer given the workspace state and the target branch. Yet today each one is re-derived by whichever model is driving the session, from prose that competes for attention with everything else in context. That is the failure mode the maintainer called out: *non-deterministic following of deterministic rules, degrading with context rot and varying by model.* Symptoms that have shown up or are latent: a skipped or duplicated counter, wrong zero-padding (`featauth-7` instead of `featauth-0007`), prefix-derivation drift, an unquoted or wrong-format timestamp, a missed collision check.

The **read side** has the same problem and is hit more often: to *read* a session file, the agent must resolve its path — and it usually knows the slice **id** (or "the active plan"), not the **slug** that completes the filename. That resolution is also prose today (AGENTS.md § Active Implementation Branches step 2: "the most recent plan whose `implementation_branch` matches … is the active context"; plan-and-implement.md step 5: "check `sessions/changes/` for related prior plans"). Same deterministic rules, same prose-replay risk.

The fix is to move the deterministic part into deterministic code: a thin `zentaizo` command surface that **resolves** an existing path and **allocates + scaffolds** a new one — so the AGENTS.md prose shrinks to *"run this command"* instead of a procedure the model must replay each time. The CLI is already a prerequisite for the workspace (see principle 2), so this removes the algorithm from prose entirely rather than relegating it to a fallback. Resolution is the primitive; creation is resolution-of-the-next-path plus a template write.

## Design principles

1. **Deterministic in the CLI; judgment in the AI.** This is the existing split stated in `api-reference-docs-layer.md` ("keep the tool deterministic; push judgment-heavy work to the AI session"). Counter arithmetic, prefix derivation, timestamp formatting, collision detection, and template instantiation are mechanical → CLI. Choosing the slug, writing the plan body, deciding *which* branch the work belongs to → AI.
2. **The CLI is a prerequisite, not an optional accelerator — so there is no by-hand fallback.** The `zentaizo` console script and the global skill ship in the *same* pip package (`[project.scripts] zentaizo = "zentaizo.cli:main"`), and `zentaizo skills install` is itself a CLI subcommand — you cannot have installed the skill, or created the workspace (`zentaizo create`), without the CLI on PATH. AGENTS.md already assumes the CLI for every other operation (`fetch`, `summarize`, `validate`, `provide-info`) with no hand-rolled alternative; session-filename allocation is treated the same. AGENTS.md keeps a one-line *description* of the filename shape so a human can read existing names, but the *procedure* to allocate one — derivation, counter scan, collision check — lives only in the code. If `zentaizo` is not found, the instruction is **"install zentaizo"** (one pointer to the README), not "do it by hand." Removing the algorithm prose entirely is the stronger form of the anti-context-rot goal: there is no deterministic logic left in prose to drift, rot, or be mis-followed.
3. **Thin, read-mostly, stdlib-only.** No new dependencies (the package has `dependencies = []`). Git access goes through the existing `try_run_git()` helper; the workspace is located with the existing `args.workspace` / `find_atlas` pattern; frontmatter is read with a minimal line scanner, not a YAML dependency.
4. **Fail loud, never guess silently.** On a cross-branch prefix collision, or an undeterminable branch, the command exits non-zero with an actionable message rather than writing a wrong file. Writing the file is the side effect; refusing is always safe.

## Command surface

There are **two distinct operations**, and conflating them was a gap in the first draft of this design:

- **Resolve (read-only)** — *"given a session identifier, what is the filename?"* Pure naming/lookup; never writes. Needed far more often than creation: every time the agent wants to *read* an existing plan, handoff, or report, it needs the deterministic path, and the agent typically knows the slice **id** (or "the active one") but not the **slug** that completes the filename.
- **Create (writes)** — allocate the next path *and* scaffold the file with frontmatter.

The resolver is the primitive; the creators are "resolve the next path, then write the template." Exposing the resolver on its own is what answers the read-side need.

### `zentaizo path` — resolve (read-only, never writes)

```
zentaizo path slice <id>        [--branch B | --prefix P] [--json]   # existing changes/ or debugging/ file for that id (globs the slug)
zentaizo path slice --next      [--branch B | --prefix P]           # the next shared-counter id stem, e.g. mcgpu-0044 (no write)
zentaizo path active            [--branch B] [--json]                # the active plan for the branch (highest open slice; see definition below)
zentaizo path handoff <id>      [--branch B | --prefix P] [--json]   # all handoffs for that slice id (globs <prefix>-<id>[a-z]*)
zentaizo path list [slice|handoff] [--branch B] [--json]             # enumerate matching files for the branch (optional convenience)
```

Prints the resolved path(s) to stdout, exit 0; exit 2 if nothing matches (or, for `--next`, on a collision / undeterminable branch). It reads `sessions/` and git only — no file is created, so it is always safe to call.

**`path active`, defined exactly** (it becomes the read primitive for "the current plan", so its ordering must be pinned, not "latest"): of the `sessions/changes/` files whose frontmatter `implementation_branch:` equals the resolved branch `B`, drop any whose `status:` is `done`, `superseded`, or `abandoned`; of what remains, the active plan is the one with the **highest slice counter `NNNN`** (counters are unique per prefix, so there is never a tie). No open plan for `B` → exit 2. Note this keys on `status`, the closeout-owned field, so a finished plan stops being "active" the moment closeout marks it `done` — matching how a human reads the directory. (`debugging/` files are excluded; "active" is about the implementation plan, and a debugging note is not the branch's working plan even though it shares the counter.)

**Slice-id form and ambiguity.** An `<id>` argument is **1–4 decimal digits, range 0–9999**; anything else is a usage error (exit 1). It is **zero-padded to four** before globbing (`43` and `0043` are the same slice), so the agent may pass the bare number it remembers. `path slice <id>` globs `{P}-{NNNN}-*` across **both** `changes/` and `debugging/` and must resolve to **exactly one** file: zero matches → exit 2 (not found); **more than one** match (only possible in a legacy or corrupt workspace where the unified counter was violated) → exit 2 listing every match, so the ambiguity surfaces rather than the tool silently picking one. The same one-file invariant applies wherever a single path is expected; `path handoff <id>` is the deliberate exception (it returns the whole `{P}-{NNNN}[a-z]*` set in letter order). `path slice --next` previews the next shared-counter id *stem* (`<prefix>-NNNN`) without writing — it deliberately stops at the stem because the directory (`changes/` vs `debugging/`) and the slug are only decided at create time by `next-change`/`next-debugging`. This is the compute-only allocation the earlier draft expressed as a `--dry-run` flag; giving it a home under `path` means there is one read verb and one write verb per concept.

### `zentaizo next-*` — create (resolve + scaffold)

One `next-*` verb per session kind, mirroring the six-directory taxonomy. `next-change` and `next-debugging` both draw from the **one shared per-branch counter** (a change and a debugging note never reuse a number — the sequence is unified across the two directories); the other kinds don't consume the counter but still get deterministic names from the tool so the agent never hand-derives a path. Each verb is `zentaizo path … --next` followed by writing the template. The write side names the concrete kind (you're making *a change* or *a debugging note*); the read side looks up by the shared counter (`path slice <id>`), because an id resolves to exactly one file across both directories.

```
zentaizo next-change    <slug> [--branch B | --prefix P] [--json]   # sessions/changes/    (consumes the shared slice counter)
zentaizo next-debugging <slug> [--branch B | --prefix P] [--json]   # sessions/debugging/  (consumes the SAME counter)
zentaizo next-handoff [id] [label] [--branch B | --prefix P] [...]  # sessions/handoffs/  (reuse slice id + auto letter; id omitted → 0000)
zentaizo next-note   <slug> [...]                                # sessions/questions/  (date-prefixed)
zentaizo next-report <slug> [...]                                # sessions/reports/    (topical slug)
```

Each prints the path of the file it created and exits 0; on collision or an undeterminable branch it prints to stderr and exits 2, writing nothing.

Worked examples (mesher-style, editable repo on branch `mc-gpu`, workspace on `main`):

```
$ zentaizo next-change --branch mc-gpu coarse-lod-fix
sessions/changes/mcgpu-0043-coarse-lod-fix.md            # scaffolded from plan-template.md

$ zentaizo next-change taxonomy-refresh                  # no --branch → workspace branch (main)
sessions/changes/main-0030-taxonomy-refresh.md

$ zentaizo next-debugging --branch mc-gpu terracing-ab   # SAME counter as changes/ → next is 0044
sessions/debugging/mcgpu-0044-terracing-ab.md

$ zentaizo next-handoff 43 codex --branch mc-gpu         # reuses slice id 0043; auto-picks the next free letter
sessions/handoffs/mcgpu-0043a-codex.md                   # "codex" is an optional label; letter "a" is the deterministic key
$ zentaizo next-handoff 43 resume --branch mc-gpu        # second handoff for the same slice → letter advances
sessions/handoffs/mcgpu-0043b-resume.md

$ zentaizo next-handoff compression-research            # no id → pre-numbered (0000); was the old "topical" case
sessions/handoffs/main-0000a-compression-research.md

$ zentaizo next-note fvdb-residency-question
sessions/questions/2026-05-27-fvdb-residency-question.md

$ zentaizo next-report multires-meshing-strategies
sessions/reports/multires-meshing-strategies.md          # scaffolded from a new report-template.md
```

And the read side — resolving an existing path to *read* it, knowing only the id (the slug is recovered for you):

```
$ zentaizo path slice 43 --branch mc-gpu                 # I know the id, not the slug
sessions/changes/mcgpu-0043-coarse-lod-fix.md

$ zentaizo path active --branch mc-gpu                   # which plan is the active context here?
sessions/changes/mcgpu-0043-coarse-lod-fix.md

$ zentaizo path handoff 43 --branch mc-gpu               # all handoffs for slice 43, in letter order
sessions/handoffs/mcgpu-0043a-codex.md
sessions/handoffs/mcgpu-0043b-resume.md

$ zentaizo path slice --next --branch mc-gpu             # what id comes next? (no write, dir-agnostic)
mcgpu-0044
```

> **Naming alternative.** The two operations could nest under one group for symmetry: `zentaizo session path …` (resolve) and `zentaizo session new {slice|handoff|note|report} …` (create), consistent with the existing `zentaizo skills {list|install|uninstall}`. The flat `zentaizo path` + `zentaizo next-*` verbs are proposed here because they read as imperatives and `next-*` was the form signed off earlier; the `session {path,new}` grouping is a drop-in rename if the flat verbs feel heavy against the ~10 existing top-level commands. Either way the resolve/create split is the substance.

## The hard part: resolving branch → prefix

`branch_prefix` is **not always the workspace repo's branch.** In the mesher workspace the workspace repo sits on `main`, but code-work plans are filed `mcgpu-*` because the prefix derives from the *editable repo's* implementation branch (`mc-gpu`), while meta/workspace plans (e.g. `main-0029`) derive from the workspace's own `main`. The tool cannot divine which case it is in — that is a judgment call — so it resolves **two separate things** by an explicit, predictable precedence: the **prefix** (which names the file) and the **branch identity** (which is written to frontmatter and drives the collision check). The flags are *not* mutually exclusive — `--prefix` overrides only the first:

1. **`--branch B`** (optionally with `--prefix P`) — the normal editable-repo form. Prefix = `derive_prefix(B)`, or `P` verbatim if `--prefix` is also given (override the derivation, keep the branch identity). Branch identity = `B`: the collision check compares against `B`, and the scaffolded frontmatter gets `implementation_branch: B`. **This is the flag the agent passes for editable-repo feature work** (`--branch mc-gpu` → `mcgpu`).
2. **`--prefix P` alone** — escape hatch with *no branch identity*. Use `P` verbatim, **skip the cross-branch collision check** (there is no branch to compare against, and supplying the prefix by hand asserts you accept responsibility for it), and write **no** `implementation_branch:` field. For the rare case where the agent already knows the exact prefix and there is no meaningful branch.
3. **Neither flag** — derive from the **workspace repo's** current branch `B0 = try_run_git(["branch", "--show-current"], cwd=workspace)`. Prefix = `derive_prefix(B0)`, branch identity = `B0`. Covers the common meta/workspace case (`main-NNNN`).

If step 3 yields an empty string (detached HEAD) or git is absent, the tool **refuses** and tells the user to pass `--branch` or `--prefix`. No silent default to `main`.

**`implementation_branch:` is always written when a branch identity exists** (cases 1 and 3) — including for the workspace's own branch (`main-0030` carries `implementation_branch: main`). The earlier "write it only when `B` differs from the default branch" rule is dropped: there is no reliable default-branch source before an atlas exists, and "always write it" needs no such source. Existing files that *lack* the field are treated as legacy (pre-CLI) and handled leniently by the collision check (below). Only case 2 (`--prefix` alone) produces a file with no branch field.

`derive_prefix()` is promoted from the reference snippet currently living only in the AGENTS.md prose into a real function in `cli.py` (lowercase → keep `[a-z0-9]` → truncate to 8, error if empty), and the AGENTS.md text then points at the CLI as its implementation.

> **Optional future convenience (not in v1):** auto-detect the branch by scanning editable repos in the atlas (`git -C <repo> branch --show-current`) and, *iff exactly one* editable repo is on a non-default branch, use it. Deferred because multiple editable repos or multiple feature branches make it ambiguous, and ambiguity here should prompt an explicit flag, not a guess.

## Counter and collision algorithm

For the counter-consuming kinds (`next-change`/`next-debugging`, and `next-handoff`'s validation):

1. Resolve prefix `P` and branch identity `B` (above).
2. List `sessions/changes/` + `sessions/debugging/` for files matching `^{P}-(\d{4})-`. The counter is **unified across both directories** (one sequence per prefix).
3. **Collision check** (skipped entirely when the prefix came from `--prefix` alone, i.e. no `B`). If matching files exist, read each one's frontmatter `implementation_branch:` with a minimal line scanner (scan the leading `---…---` block for the key). A file that **has** the field and whose value ≠ `B` → **prefix collision**: exit 2 naming both branches, write nothing. A file **missing** the field is legacy (pre-CLI) — it cannot be compared, so it does **not** trigger a collision (lenient). (Two different branch names can derive to the same 8-char prefix; this is the only case the convention does not prevent structurally, so the tool enforces it where it has the evidence to.)
4. Otherwise next counter = `max(existing) + 1`, or `0001` if none. Zero-pad to 4.
5. Compose `{P}-{NNNN}-{slug}.md` in `changes/` (`next-change`) or `debugging/` (`next-debugging`).

Handoff naming is covered in its own section below; it reuses a slice id (not the counter) and adds a deterministic per-slice letter.

`next-note` (questions) and `next-report` (reports) don't touch the counter: `YYYY-MM-DD-{slug}.md` (today's UTC date) and `{slug}.md` respectively.

A minimal frontmatter reader (≈15 lines: open file, if first line is `---` read until the next `---`, split `key: value`) is all that's needed — no YAML dependency, consistent with the repo's stdlib-only stance.

## Handoff naming: per-slice letter + optional label

This **supersedes** the round-2 handoff convention (`<branch_prefix>-NNNN-<role>.md`, where `<role>` was the implementing agent or handoff type). That scheme had two problems the CLI exposes: it relied on the agent *choosing and spelling a role consistently* (a judgment, the thing we're removing), and it had no clean answer when a slice needs **multiple handoffs of the same kind across several turns** (a second `-resume` would collide).

The replacement:

```
<branch_prefix>-NNNN<letter>[-<label>].md
```

- **`NNNN`** — the paired slice's id, **reused** (never consumes the per-branch counter). A handoff that is *not yet tied to a numbered slice* — a restart prompt that plans future work, a multi-slice/phase-transition handoff — uses **`0000`**. This subsumes what round 2 called the "topical-slug fallback": those files (`compression-research-restart`, `sliceb-restart`, `phase1k-to-phase1n` in the dogfooding workspace) are simply slice `0000` handoffs. There is no separate fallback code path.
- **`<letter>`** — a deterministic per-slice ordinal, **`a`–`z`**, the *uniqueness key*. The CLI globs `{P}-{NNNN}[a-z]*`, finds the highest letter in use, and takes the next (first handoff for a slice → `a`). Lowercase only: case-insensitive filesystems (macOS APFS, Windows NTFS) would treat `…0041a` and `…0041A` as one file, so the uppercase half of `[a-zA-Z]` is a latent collision and is excluded. 26 is far more than any slice will see; the unreachable overflow is `aa`, `ab`, …
- **`<label>`** — an **optional, free** descriptive slug, the agent's discretion (a topic, a handoff type, an agent name, or nothing). It is *not load-bearing* — the letter already guarantees order and uniqueness — so the agent never has to spell it *correctly*, only *helpfully*. This mirrors the blog-post-URL pattern: a deterministic id the router resolves on, followed by a human-readable slug it ignores.

`next-handoff [id] [label]`: a numeric first argument is the slice id; a non-numeric first argument is the label (id defaults to `0000`). For `id ≠ 0000` the tool verifies a paired plan `{P}-{id}-*.md` exists in `changes/`/`debugging/` and refuses otherwise (no orphan handoffs); `0000` skips that check. It then allocates the next letter and writes the stub. `path handoff <id>` lists `{P}-{id}[a-z]*` in letter order.

## Scaffolding: what the tool fills vs. what the agent fills

"Scaffold the file" means the tool **creates** the file with everything deterministic already filled, leaving only prose and judgment fields for the agent. The boundary, per kind:

| Kind | Template | Tool fills (deterministic) | Agent fills (judgment) |
|---|---|---|---|
| `changes/`, `debugging/` | `skills/plan-template.md` | `status: planned`; `created`/`updated` = now UTC ISO (quoted); `branch_prefix: P`; `implementation_branch: B` whenever a branch identity was resolved (always, except the `--prefix`-alone escape hatch) | title, problem/scope/approach/criteria, `editable_repos`, `implementation_base` (divergence sha) + `implementation_outdir` (left as commented TODO, as in the template today) |
| `handoffs/` | minimal stub | heading `# {P}-{NNNN}{letter} handoff` (+ label if given); `Date:` = now UTC; a `Spec:` pointer line to the paired plan path (omitted for `0000`) | the actual handoff prompt body |
| `questions/` | minimal stub | heading + `Date:`; empty `## Question` / `## Answer` / `## Sources` sections | the Q&A content |
| `reports/` | **new** `skills/report-template.md` | frontmatter `title` (from slug), `status: living`, `current_as_of`, `created`/`updated`, empty `related:` | the synthesis body, `destined_for:` |

`next-debugging` reuses `plan-template.md` deliberately. Despite the "save the trace" phrasing in `plan-and-implement.md`, debugging notes in practice are plan-*shaped*: the two in the dogfooding workspace (`mcgpu-0025`, `mcgpu-0038`) carry the full plan frontmatter and a `## Plan` (Context / Hypotheses / Investigation protocol / **Acceptance criteria** / Verification) + `## Outcome` (Verdict / Evidence / Recommendation) structure — i.e. "a plan for an investigation." So one template fits both, and the `plan-and-implement.md` "save the trace" wording should be nudged to match (it undersells what a debugging note is). A trace too quick to warrant the structure can just leave sections empty.

Two follow-on artifacts this requires:

- **Add `report-template.md`** to `templates/skills/` (and have `install_skills_into_workspace` / `create_workspace` copy it). It needs **no new `package-data` entry** — the existing `templates/skills/*.md` glob already bundles any new `.md` there. Its frontmatter must mirror the round-2 `reports/` charter **field-for-field** (`title`/`status`/`current_as_of`/`created`/`updated`/`related`/`destined_for`), since the charter is the documented contract the scaffold has to satisfy.
- **Pre-existing `package-data` bug, fixed alongside this doc.** The global-skill entries were enumerated file-by-file — `templates/global-skills/zentaizo/SKILL.md` and `agents/*.yaml` — which **omitted `upgrade-zentaizo.md`**, the sibling that `SKILL.md` itself tells the agent to read. `skills install` copies the whole directory with `shutil.copytree`, so a *source* checkout was fine, but a **wheel built from `pyproject.toml` dropped `upgrade-zentaizo.md`** — a `pip install`'d zentaizo installed a skill pointing at a missing file. The glob is now `templates/global-skills/zentaizo/*.md`, so both `SKILL.md` and `upgrade-zentaizo.md` (and any future sibling) ship. Independent of the new commands, surfaced by Codex review; fixed in the same change that added this revision.
- The handoff/question stubs are small enough to live as inline strings in `cli.py` rather than template files (they are headers, not structured documents). Reasonable either way; inline keeps the template count down. Note these stubs introduce file structure (`Date:`/`Spec:` lines, `## Question`/`## Answer`/`## Sources`) that the current charters don't spell out — so the relevant charter prose should gain a one-line mention of the stub shape, or the stubs stay truly minimal (heading + `Date:` only).

The tool **never** fills judgment fields with a guess. `implementation_base` (the merge-base/divergence short-sha) is intentionally left as the template's existing commented placeholder: computing it would require knowing the editable repo path and its default branch, and getting it subtly wrong is worse than leaving the agent to fill it.

## Flags and exit codes

- Compute-without-writing is `zentaizo path … --next`, not a `--dry-run` flag on the creators — one read verb, one write verb per concept, no two-ways-to-do-it.
- `--json` (on both `path` and `next-*`) — emit `{"path","kind","branch","prefix","counter","created","wrote":bool}` instead of the bare path, for agents that prefer structured parsing (resists prose-parsing mistakes; aligns with the agent-facing-verb instinct in `ideas-worth-borrowing.md` §4). `path list` emits a JSON array.
- Exit `0` success, `2` not-found (`path`) / collision / undeterminable branch / missing paired plan, `1` usage error. Errors go to stderr; path(s) go to stdout so `$(zentaizo path slice 43)` and `$(zentaizo next-change …)` are both safe to capture.
- Creators refuse to overwrite: if the composed path already exists, exit 2 (don't clobber). The final create uses exclusive-create semantics so a same-instant double-run loses cleanly rather than truncating.

## The payoff: what shrinks in `AGENTS.md`

This is the point of the exercise. `workspace_agents()` § Filename Convention today renders ~50 lines of procedure (the `derive_prefix` Python block, the "Finding the next counter value" shell snippet, the "Plan-creation collision check" numbered steps, the "Parallel-agent safety" note). After this lands, that collapses to roughly:

> Session files are allocated by the CLI. Run `zentaizo next-change <slug>` for a plan, `zentaizo next-debugging <slug>` for a debugging note, `zentaizo next-handoff <id> [label]` for a handoff (omit the id for a pre-numbered one), `zentaizo next-note`/`next-report` for the others; pass `--branch <impl-branch>` for editable-repo work. To read an existing file, `zentaizo path slice <id>` (or `zentaizo path active`). The commands derive the per-branch prefix, allocate the shared counter, run the cross-branch collision check, and scaffold the file with correct frontmatter. See `zentaizo path --help` / `zentaizo next-change --help`.
>
> (Counter-keyed names look like `<prefix>-NNNN-<slug>.md`, so existing files are easy to read at a glance. If `zentaizo` is not on your PATH, install it — see the README — rather than allocating a name by hand.)

The deterministic logic now has **exactly one home** (the code); the prose keeps only a one-line shape *descriptor* (to read names) and an install pointer — no allocation *procedure*. The model is asked to *invoke*, never to *replay*. The status-frontmatter schema already moved to the skill/template in round 2, so the timestamp/`status`/`branch_prefix` fields the tool now fills are consistent with where they're documented.

So the agent neither re-derives a name to *write* nor globs to *read* — both sides go through the same deterministic resolver, which guarantees the read path and write path agree on the naming rule by construction.

### Every instruction touchpoint that must change

The CLI is only "aligned" if *all* the prose that currently hand-composes a path or describes allocation/lookup mechanics is updated in lockstep — otherwise the instructions contradict the tool. The complete inventory (verified against the current text):

**AGENTS.md (generated by `workspace_agents()`):**
- § **Filename Convention** — drop the `derive_prefix` block, the "Finding the next counter value" snippet, the "Plan-creation collision check" steps, and the "Parallel-agent safety" prose; keep a one-line *shape descriptor* + install pointer.
- § **Recording Work in `sessions/`** charters — the `handoffs/` and `reports/` charters embed allocation/frontmatter mechanics (and the `handoffs/` one is the **superseded** `<role>` scheme); rewrite both to the new naming and "the CLI allocates/scaffolds this," keeping only *what each dir is for*.
- § **Active Implementation Branches, step 2** → `zentaizo path active`; keep only *why* active-branch state lives in checked-out state + frontmatter, not the lookup mechanics.
- § **From Brainstorming to Plan, steps 3 & 4** — hand-compose the `changes/` and `handoffs/` paths; point at `next-change` / `next-handoff`.

**`skills/plan-and-implement.md`:**
- "Drafting the plan" **step 1** (hand-composes the `changes/` path + tells the agent to read the derivation/counter/collision rules) → `zentaizo next-change`.
- **Step 2** (fill `status`/`created`/`updated`/`branch_prefix`) → these are CLI-filled; shrink to "fill `editable_repos` + `implementation_base` + the body."
- "Handing off to an implementing agent" **section** (hand-composes the `handoffs/` path, prescribes the `<agent>` name) → `zentaizo next-handoff <id> [label]`.
- Executing **step 4** (hand-composes the `questions/` *and* `debugging/` paths) → `next-note` / `next-debugging`.
- Pre-flight **step 5** ("check for related prior plans") → `zentaizo path`.
- The "save the trace" wording (When-to-run + step 4) → nudge to acknowledge debugging notes are plan-shaped.

**Generated README (`workspace_readme()`):** steps 5 & 6 hand-compose every session path → point at the create verbs.

**`skills/plan-template.md`:** silently becomes a **CLI-consumed contract** — the scaffolder string-replaces its `created:` / `branch_prefix:` / commented `implementation_branch:` lines. Add a comment marking it as such so a future edit doesn't break the scaffolder.

**`templates/global-skills/zentaizo/`:** `SKILL.md` should list the new verbs alongside `validate`/`status`/`fetch`; `upgrade-zentaizo.md` should know the convention is now CLI-backed (and that bringing a workspace forward includes the one-time rename of existing handoffs to the letter scheme).

Build-order step 5 (below) is where this inventory is executed — as one commit, after the commands exist, so the instructions never describe a tool that isn't there yet.

## Implementation notes

- **One resolver core, two thin command layers.** A pure `resolve_session_path(workspace, kind, *, id=None, role=None, slug=None, branch=None, prefix=None, want_next=False, active=False) -> ResolveResult` does all the naming/lookup. `path_workspace(args)` prints its result; the `next_*_workspace(args)` creators call it with `want_next=True` then write the template. Both register as subparsers with the standard `workspace` positional (`nargs="?", default="."`).
- Reuse: `try_run_git`. These commands work even before an atlas exists (a fresh workspace has `sessions/` but no atlas), so they must *not* hard-require the atlas the way `status` does — gate only on the `sessions/` dirs existing. (`--branch`/auto-detect that reads editable repos from the atlas degrades gracefully when the atlas is absent.)
- New small helpers feeding the resolver: `derive_prefix(branch)`, `read_frontmatter(path) -> dict` (line scanner), `scan_slices(workspace, prefix) -> list[int]`, `detect_collision(workspace, prefix, branch) -> str|None`, `find_slice_file(workspace, prefix, id) -> Path|None`, `find_active_plan(workspace, branch) -> Path|None`.
- `report-template.md` added to `package-data` and copied by `install_skills_into_workspace` / `create_workspace`.

## Edge cases and non-goals

- **Same-branch concurrency** is *not* solved — two agents on the same branch can both compute `NNNN+1`. The convention already says "one agent per branch at a time; git worktrees as the escape hatch." The exclusive-create on the final write makes a same-instant collision fail cleanly, but the counter race is inherent and out of scope.
- **Detached HEAD / no git / bare workspace** → refuse with guidance to pass `--branch`/`--prefix`. Never default to `main`.
- **Slug normalization (one rule, not "lightly").** Because the slug lands in a path the tool *writes*, the normalization is pinned, not best-effort: lowercase to ASCII; replace every run of non-`[a-z0-9]` characters with a single `-`; strip leading/trailing `-`. Then **reject** (usage error, exit 1) if the result is empty, or if the *original* input contained a path separator (`/` or `\`), `..`, or a leading `.` — i.e. no path traversal and no dotfiles, caught before normalization can mask them. The tool normalizes but never *invents* a slug; a missing or empty slug is a usage error. (`next-handoff`'s optional label takes the same normalization; `next-note`/`next-report` slugs too.)
- **Not a migration tool.** Renaming existing files when a convention changes remains the `upgrade-zentaizo` skill's job.

## Testing

Unit tests (extend `tests/test_cli.py`): `derive_prefix` table (reuse the AGENTS.md example rows); counter scan with files spread across `changes/`+`debugging/`; first-on-branch → `0001`; collision detection (same prefix, different `implementation_branch`) → exit 2, no write; a legacy file **missing** `implementation_branch:` does **not** trigger a collision (lenient); `--prefix` alone **skips** the collision check and writes a file with no `implementation_branch:` field. Resolver: `path slice <id>` recovers the on-disk slug; bare `43` and padded `0043` resolve identically; an out-of-range / non-numeric id → exit 1; `path slice <id>` for a missing id → exit 2; **two** files sharing an id across `changes/`+`debugging/` (corrupt workspace) → exit 2 listing both; `path slice --next` prints the next path **and writes nothing** (assert directory is unchanged). `path active`: with several `changes/` plans matching `implementation_branch`, picks the **highest-counter** one whose `status` is not `done`/`superseded`/`abandoned`, ignores non-matching branches, ignores `debugging/`, and exits 2 when every matching plan is closed. Slug: `"Coarse LOD Fix"` → `coarse-lod-fix`; a slug containing `/`, `..`, or a leading `.` → exit 1 (no file written). Creators: `--json` shape; `next-handoff <id>` allocates `a` then `b` for a second handoff on the same slice; `next-handoff <id>` for `id ≠ 0000` refuses without a paired plan, while `next-handoff <label>` (no id → `0000`) does not; lowercase-only letters; detached-HEAD/no-branch refusal; scaffolded frontmatter has a quoted UTC timestamp, correct `branch_prefix`, and an `implementation_branch:` line even for the workspace branch; refuse-to-overwrite. A round-trip test: `path slice --next` → `next-change` → `path slice --next` advanced by one → `next-debugging` lands on that same next id (shared counter), and `path slice <new-id>` resolves the file just created in either directory.

## Build order

1. The resolver core + pure helpers (`derive_prefix`, `read_frontmatter`, `scan_slices`, `detect_collision`, `find_slice_file`, `find_active_plan`), with unit tests (no I/O beyond reading `sessions/`).
2. `zentaizo path` (read-only) over the resolver: `slice <id>`, `slice --next`, `active`, `handoff`, optional `list`; `--json`. Read-only and reusable, so it lands first and is independently useful for the read side even before any creator exists.
3. `next-change` + `next-debugging` = resolver `--next` + scaffold from `plan-template.md` (they share the counter). The highest-value creators — ship and dogfood before the rest.
4. `report-template.md` + `next-report`; `next-handoff` (per-slice letter allocation, `0000` for pre-numbered, paired-plan validation for `id ≠ 0000`); `next-note`. (The `package-data` glob no longer needs touching here — the global-skills `*.md` fix already landed with this doc, and `report-template.md` is covered by the existing `templates/skills/*.md` glob.)
5. Execute the **full instruction-touchpoint inventory** above as one commit (AGENTS.md §§ Filename Convention / Recording Work charters / Active Implementation Branches / From Brainstorming; all the `plan-and-implement.md` steps; the generated README; the `plan-template.md` contract comment; `SKILL.md` + `upgrade-zentaizo.md`) — keeping only one-line shape descriptors + an "install zentaizo" pointer and removing every allocation/lookup *procedure*. Update the tests that assert the old prose. Doing it as one commit, after the commands exist, keeps the instructions from ever describing a tool that isn't there.

## Related

- `api-reference-docs-layer.md` — the deterministic-CLI / judgment-AI split this follows.
- `ideas-worth-borrowing.md` §4 ("an explicit agent-facing retrieval verb") — sibling thin verb; `--json` here and a future `zentaizo get`/`search` should share an output convention.
- `zen-segmend-mesher-template-integration-round-2.md` — where this idea was first captured as deferred.
