# Deterministic efforts and session paths: `zentaizo effort`, `zentaizo path`, `zentaizo next-*`

_Design doc. Drafted 2026-05-27; revised 2026-05-27 after a Codex review. **Revised again 2026-05-28: the branch-derived prefix is replaced by a CLI-allocated, agent-chosen `effort` label backed by a `sessions/efforts.json` registry.** This is the change that makes the workspace handle more than one editable repo per change, and it deletes the doc's hardest section (resolving branch → prefix) rather than patching it. Status: proposed (not yet implemented)._

A thin, deterministic CLI for three things the agent does with sessions: **name a body of work** (an *effort*), **resolve** an existing session file to read it, and **allocate + scaffold** a new one — replacing the prose procedures in `AGENTS.md` and `skills/plan-and-implement.md` that an LLM re-derives (non-deterministically, with context rot) each session.

## Problem

Two deterministic chores are currently **procedures the AI executes from prose**, re-derived each session from instructions that compete for attention with everything else in context. That is the failure mode the maintainer called out: *non-deterministic following of deterministic rules, degrading with context rot and varying by model.*

1. **Allocating a session filename.** `AGENTS.md` § Filename Convention tells the agent to derive an 8-char prefix from the git branch with a specific lowercase/strip/truncate rule, scan for the highest existing counter for that prefix, add one, zero-pad to four digits, run a cross-branch collision check by reading other files' frontmatter, then hand-write the file with `status: planned`, a correctly-formatted UTC timestamp, and the prefix echoed into frontmatter. Every step is mechanical, yet each is re-derived by whichever model is driving — with latent symptoms: a skipped/duplicated counter, wrong zero-padding (`featauth-7` not `featauth-0007`), prefix-derivation drift, an unquoted timestamp, a missed collision check.

2. **Resolving a path to read a file.** To *read* a session file the agent must reconstruct its path — and it usually knows the slice **id** (or "the active plan"), not the **slug** that completes the filename. That resolution is also prose today, with the same replay risk.

### The deeper problem: prefixes were tied to a single branch

The first draft of this design derived the filename prefix from *the editable repo's implementation branch*. That assumption does not survive the reality the maintainer flagged: **more than one repo under `repos/` can be editable at once** — e.g. integrating a new authentication/authorization framework across an API, a web client, and an SDK. When a single body of work spans several editable repos:

- **There is no single branch to derive a prefix from.** The repos may even sit on differently-named branches (`feat/auth` in one, `auth-migration` in another).
- **Branch prefixes can collide** — two distinct branches can truncate to the same 8 characters — which is why the first draft needed a whole cross-branch collision-check subsystem.
- **Branch names are mutable** — a rename silently orphans the naming link.

The first draft answered this with its largest section, *"The hard part: resolving branch → prefix"* — three precedence rules over `--branch`/`--prefix`, a detached-HEAD refusal, a `derive_prefix()` truncation function, and a frontmatter-reading collision check. All of that machinery exists to paper over a coupling that was wrong: **the unit of work is not a branch, it is an *effort*, and an effort is bigger than any one repo's branch.**

## The fix: name the effort, don't derive it from a branch

Replace the branch-derived prefix with a **label that names an effort** — a logical body of related work that may span several editable repos. The label is:

- **Chosen by the agent**, a short word it already has in hand while producing the slice (the design's "judgment in the AI" half). A curated themed wordlist (well-known Japanese words an English speaker knows — `sushi`, `tempura`, `katana`, `dojo`, …) is shipped only as a *suggestion* fallback when the agent has no preference (`zentaizo effort new` with no label proposes the next unused word).
- **Reserved by the CLI** in a single registry file, `sessions/efforts.json`, which guarantees uniqueness and refuses a duplicate (the design's "deterministic in the CLI" half). The CLI owns uniqueness and the counter; the agent owns the word and the prose.
- **Decoupled from git branches.** The label is the effort's identity; the branches the effort opens in each repo are an implementation detail recorded *against* the effort, not encoded in its name. You do not conflate a branch with an effort: a branch is named by each repo's own conventions and need not contain the label.

This collapses, rather than patches, the hard part:

| First draft (branch-derived) | This draft (effort-label) |
|---|---|
| `derive_prefix()` lowercase/strip/truncate rule | gone — the agent supplies the word; the CLI reserves it verbatim (after slug-normalization) |
| three-rule `--branch`/`--prefix` precedence | gone — one `--label` (default: the current effort) |
| detached-HEAD / no-git refusal | gone — labels do not depend on git at all |
| cross-branch prefix collision check + legacy leniency | gone — `effort new` refuses a taken label up front; full words don't truncate-collide |
| "which branch is the prefix?" judgment | answered once, explicitly, at `effort new` |

What the first draft put in the *filename* (a hint about which repo/branch the work touches) moves to **queryable frontmatter and the registry**, which is more reliable than parsing a prefix — and is exactly the "label → which repos need work" mapping downstream tooling wants.

## Design principles

1. **Deterministic in the CLI; judgment in the AI.** Counter arithmetic, timestamp formatting, uniqueness, `base`-sha computation, and template instantiation are mechanical → CLI. Choosing the effort word, writing the description and plan body, deciding which repos an effort touches → AI.
2. **The CLI is a prerequisite, not an optional accelerator — so there is no by-hand fallback.** The `zentaizo` console script and the global skill ship in the same pip package; `zentaizo skills install` and `zentaizo create` both go through the CLI, so you cannot have a workspace without the CLI on PATH. Session-filename allocation is treated like every other operation (`fetch`, `summarize`, `validate`): if `zentaizo` is missing, the instruction is **"install zentaizo"** (one README pointer), not "do it by hand." Removing the algorithm prose entirely is the stronger form of the anti-context-rot goal.
3. **Thin, read-mostly, stdlib-only.** No new dependencies (`dependencies = []`). Git access goes through the existing `try_run_git()`; the workspace is located with the existing `args.workspace` pattern; frontmatter and the registry are read with a minimal line scanner and `json`, not a YAML dependency.
4. **Fail loud, never guess silently.** A taken label, an undeterminable effort, a missing paired plan → exit non-zero with an actionable message rather than writing a wrong file. Writing is the side effect; refusing is always safe.

## Core concept: the effort

An **effort** is a named body of related work. In the dogfooding `zen-segmend-mesher` workspace, the two efforts were `main` (workspace-meta work — atlas, summaries, conventions) and `mcgpu` (the GPU mesher feature). Under this design those become: a reserved **`main`** effort (workspace-meta; no editable repos), and a themed-label effort (say `katana`) with the mesher repo registered on its `mc-gpu` branch.

An effort has identity and metadata, owned by the registry:

- `label` — the agent-chosen word; the slice-filename prefix and the frontmatter `label:`.
- `description` — what the effort is, in one line (agent-supplied at `effort new`).
- `status` — `open` or `closed`. The single `open` effort (other than `main`) is the default for `next-*`; closing one is explicit.
- `repos` — a map of `{ <repo-name>: { branch, base } }`: the branch this effort uses in each editable repo, and the divergence base sha. **This is the canonical "label → which repos need work" mapping.**
- `created` / `updated` — UTC ISO timestamps.

The registry also tracks **`current`** — the effort that `next-*` and `path` default to when `--label` is omitted (a git-`HEAD`-like pointer, set by `effort new`/`effort switch`). This is the explicit workspace state that replaces "the checked-out branch" as the signal for *which effort am I on* — deterministic and queryable, never inferred.

### The registry: `sessions/efforts.json`

Machine-and-agent-authored, boring JSON (consistent with `zentaizo.lock.json`). `zentaizo create` pre-seeds it with a single `main` effort, so a fresh workspace always has a `current`. A legacy workspace without the file is handled gracefully: the tool synthesizes a `main` effort and treats any existing `<label>-NNNN-*` filename as reserving that label (so a pre-CLI workspace migrates without bookkeeping).

```json
{
  "version": 1,
  "current": "katana",
  "efforts": [
    {
      "label": "main",
      "description": "Workspace-meta work: atlas, summaries, conventions.",
      "status": "open",
      "repos": {},
      "created": "2026-05-28T17:00:00Z",
      "updated": "2026-05-28T17:00:00Z"
    },
    {
      "label": "katana",
      "description": "Integrate the new auth/authz framework across API, web, and SDK.",
      "status": "open",
      "repos": {
        "shortener-api":    { "branch": "feat/auth",      "base": "a1b2c3d" },
        "shortener-web":    { "branch": "feat/auth",      "base": "e4f5a6b" },
        "shortener-client": { "branch": "auth-migration", "base": "0099fed" }
      },
      "created": "2026-05-28T17:05:00Z",
      "updated": "2026-05-28T18:30:00Z"
    }
  ]
}
```

**Division of authority — no field lives in two places:**

- The **filesystem** owns slice numbering: the next counter for `katana` is `max(NNNN for katana-NNNN-*) + 1`, globbed across `changes/` + `debugging/`. The registry does **not** store the counter, so creating a slice never writes the registry — keeping it a low-frequency, low-conflict file (it changes only on `effort new` / `set-branch` / `close`).
- The **registry** owns effort identity and the per-repo `branch`/`base`. A slice's frontmatter names only `label` (which effort) and `editable_repos` (the subset of that effort's repos *this slice* touches, by name); the branch/base are looked up from the registry, never duplicated into the slice, so nothing can drift.

## Command surface

Three groups: `zentaizo effort` (manage the effort + read its info), `zentaizo path` (resolve a single file path, read-only), `zentaizo next-*` (allocate + scaffold a file).

### `zentaizo effort` — manage and read efforts

```
zentaizo effort new [label] [--describe TEXT] [--repo NAME[=BRANCH]]... [--json]
zentaizo effort switch <label>                                    [--json]
zentaizo effort show   [label]                                    [--json]   # default: current
zentaizo effort list                                              [--json]
zentaizo effort set-branch <label> --repo NAME=BRANCH [--base SHA] [--json]
zentaizo effort close  <label>                                    [--json]
```

- **`effort new`** — the agent proposes a word; the tool slug-normalizes it, refuses if it is already a registered label *or* already in use by an existing `<label>-NNNN-*` file (exit 2 with the conflicting effort's info), else appends the effort and makes it `current`. With no `label`, it allocates the next unused word from the themed list. `--describe` records the one-line description (judgment the agent supplies). Each `--repo NAME=BRANCH` registers a branch and computes its `base` (below); `--repo NAME` with no branch records the repo with a null branch for later `set-branch`. **This is the step that captures intent — what the effort is and which repos it touches — so `next-change` can stay purely mechanical.**
- **`effort switch`** — repoint `current` (exit 2 on unknown label). The git-checkout analogue.
- **`effort show`** — print the effort's description, status, `repos` map, and the slices/handoffs that belong to it (globbed in counter/letter order). The agent's read verb for *"what is this effort and where does its work live?"* Defaults to `current`.
- **`effort list`** — enumerate efforts (label, status, repo count, description). The read verb for *"what efforts exist / which is current?"*
- **`effort set-branch`** — register or update a repo's branch on an existing effort, computing `base` if `--base` is not given. The answer to *"a branch was opened for this effort later — record it."* (exit 2 on unknown label or a repo not in the atlas).
- **`effort close`** — set `status: closed`. Does not touch `current`; `next-*` refuses to use a closed current effort and tells you to `switch` or `new`.

**Computing `base`.** Because the registry knows the repo (`repos/<name>`) and the atlas knows its pinned `ref`, the tool computes `base = git -C repos/<name> merge-base <branch> <ref>` (short sha) when the repo is fetched and the branch exists. This turns the `implementation_base` field — which the first draft deliberately left for the agent to fill — into a machine-filled value. If the repo is not fetched or the branch is absent, `base` stays `null` and is filled by a later `set-branch`; never guessed.

The tool **never** creates the git branch (that is repo-specific judgment, and the design keeps git *mutation* out). It records the branch name you opened; you run `git checkout -b` yourself.

### `zentaizo path` — resolve (read-only, never writes)

```
zentaizo path slice  <id>  [--label L] [--json]   # the changes/ or debugging/ file for that id in the effort
zentaizo path slice --next [--label L]            # the next id stem, e.g. katana-0044 (no write)
zentaizo path active       [--label L] [--json]   # the active plan for the effort (highest open slice)
zentaizo path handoff <id> [--label L] [--json]   # all handoffs for that slice id, in letter order
```

Everything defaults to the **current** effort; `--label` overrides. Prints the resolved path(s) to stdout, exit 0; exit 2 if nothing matches (or, for `--next`, on an undeterminable effort). Reads `sessions/` and the registry only — no file is created, so it is always safe to call.

**`path active`, defined exactly.** Of the `sessions/changes/` files whose frontmatter `label:` equals the resolved effort, drop any whose `status:` is `done`, `superseded`, or `abandoned`; of what remains, the active plan is the one with the **highest counter `NNNN`** (counters are unique per label, so there is never a tie). No open plan → exit 2. This keys on `status`, the closeout-owned field, so a finished plan stops being "active" the moment closeout marks it `done`. (`debugging/` is excluded — "active" is about the implementation plan.)

**Slice-id form and ambiguity.** An `<id>` is **1–4 decimal digits, range 0–9999** (else usage error, exit 1), **zero-padded to four** before globbing (`43` and `0043` are the same slice), so the agent may pass the bare number it remembers. `path slice <id>` globs `{label}-{NNNN}-*` across **both** `changes/` and `debugging/` and must resolve to **exactly one** file: zero → exit 2; more than one (only possible in a corrupt workspace where the unified counter was violated) → exit 2 listing every match. `path handoff <id>` is the deliberate exception — it returns the whole `{label}-{NNNN}[a-z]*` set in letter order. `path slice --next` previews the next id *stem* (`{label}-NNNN`) without writing — it stops at the stem because the directory (`changes/` vs `debugging/`) and the slug are only decided at create time.

### `zentaizo next-*` — create (resolve + scaffold)

One `next-*` verb per session kind. `next-change` and `next-debugging` draw from the **one shared per-label counter** (a change and a debugging note never reuse a number — the sequence is unified across the two directories). The other kinds don't consume the counter but still get deterministic names so the agent never hand-derives a path.

```
zentaizo next-change    <slug> [--label L] [--json]      # sessions/changes/   (consumes the shared counter)
zentaizo next-debugging <slug> [--label L] [--json]      # sessions/debugging/ (consumes the SAME counter)
zentaizo next-handoff <id> [topic] [--label L] [--json]  # sessions/handoffs/  (reuse slice id + auto letter)
zentaizo next-note   <slug> [--json]                     # sessions/questions/ (date-prefixed; no effort)
zentaizo next-report <slug> [--json]                     # sessions/reports/   (topical slug; no effort)
```

`--label` defaults to the **current** effort; the command prints which effort it used so the choice is never silent. Each prints the path of the file it created and exits 0; on an undeterminable/closed effort or a missing paired plan it prints to stderr and exits 2, writing nothing.

Worked examples (auth migration across three editable repos; workspace repo on `main`):

```
$ zentaizo effort new katana --describe "Integrate the new auth/authz framework" \
      --repo shortener-api=feat/auth --repo shortener-web=feat/auth
Effort 'katana' created and set as current. base shortener-api=a1b2c3d, shortener-web=e4f5a6b.

$ zentaizo next-change token-rotation                   # uses current effort 'katana'
sessions/changes/katana-0001-token-rotation.md          # scaffolded from plan-template.md (label: katana)

$ zentaizo next-change web-login-form                   # same effort, next shared counter
sessions/changes/katana-0002-web-login-form.md

$ zentaizo next-debugging stale-session-cookie          # SAME counter as changes/ → next is 0003
sessions/debugging/katana-0003-stale-session-cookie.md

$ zentaizo effort set-branch katana --repo shortener-client=auth-migration   # a branch opened later
Recorded shortener-client=auth-migration (base 0099fed) on effort 'katana'.

$ zentaizo next-handoff 1 codex                         # reuses slice id 0001; auto-picks the next free letter
sessions/handoffs/katana-0001a-codex.md                 # "codex" is an optional topic; the letter is the key

$ zentaizo next-change taxonomy-refresh --label main    # workspace-meta work on the reserved 'main' effort
sessions/changes/main-0030-taxonomy-refresh.md

$ zentaizo next-note fvdb-residency-question            # no effort/counter
sessions/questions/2026-05-28-fvdb-residency-question.md

$ zentaizo next-report auth-rollout-findings            # no effort/counter
sessions/reports/auth-rollout-findings.md
```

And the read side — knowing only the id, the slug is recovered for you:

```
$ zentaizo path slice 1                                 # current effort 'katana'; I know the id, not the slug
sessions/changes/katana-0001-token-rotation.md

$ zentaizo path active                                  # which plan is the active context here?
sessions/changes/katana-0002-web-login-form.md

$ zentaizo effort show                                  # what is this effort + which repos/branches?
katana (open) — Integrate the new auth/authz framework
  shortener-api    feat/auth      @ a1b2c3d
  shortener-web    feat/auth      @ e4f5a6b
  shortener-client auth-migration @ 0099fed
  slices: katana-0001 (done), katana-0002 (in-progress), katana-0003 (debugging)

$ zentaizo path slice --next                            # what id comes next? (no write, dir-agnostic)
katana-0004
```

> **Naming alternative.** The verbs could nest for symmetry: `zentaizo session path …` / `zentaizo session new …`, consistent with `zentaizo skills {list,install}`. The flat `path` + `next-*` verbs are proposed here because they read as imperatives and `next-*` was signed off earlier; the grouping is a drop-in rename. The `effort` group is a genuine group (it has several read/write subcommands), so it nests regardless.

## Counter and collision algorithm

For the counter-consuming kinds (`next-change`/`next-debugging`, and `next-handoff`'s validation):

1. Resolve the effort label `L` (= `--label`, else `current`). Refuse if `L` is unknown or `closed` (exit 2, write nothing).
2. List `sessions/changes/` + `sessions/debugging/` for files matching `^{re.escape(L)}-(\d{4})-`. The counter is **unified across both directories** (one sequence per label). The `-\d{4}-` structure means labels never cross-match (`do` matches `do-0001-…` only, never `dojo-0001-…`).
3. Next counter = `max(existing) + 1`, or `0001` if none. Zero-pad to 4.
4. Compose `{L}-{NNNN}-{slug}.md` in `changes/` (`next-change`) or `debugging/` (`next-debugging`).

**No cross-branch collision check exists** — it was an artifact of branch-derived prefixes that could truncate-collide. `effort new` already refused a duplicate label up front, and full agent-chosen words do not truncate, so uniqueness is guaranteed at reservation time. This is the single biggest simplification of the rewrite.

A minimal frontmatter reader (≈15 lines: if the first line is `---`, read until the next `---`, split `key: value`) reads `label:`/`status:` — no YAML dependency, consistent with the stdlib-only stance.

## Handoff naming: per-slice letter + optional topic

```
<label>-NNNN<letter>[-<topic>].md
```

- **`NNNN`** — the paired slice's id, **reused** (never consumes the per-label counter). A handoff not tied to a numbered slice — a restart prompt, a multi-slice/phase-transition handoff — uses **`0000`**.
- **`<letter>`** — a deterministic per-slice ordinal `a`–`z`, the **uniqueness key**. The CLI globs `{L}-{NNNN}[a-z]*`, finds the highest letter in use, and takes the next (first handoff → `a`). Lowercase only: case-insensitive filesystems (APFS, NTFS) would treat `…0041a`/`…0041A` as one file, so uppercase is a latent collision and excluded. The unreachable overflow past `z` is `aa`, `ab`, …
- **`<topic>`** — an **optional, free** descriptive slug (a topic, a handoff type, an agent name, or nothing). It is *not load-bearing* — the letter already guarantees order and uniqueness — so the agent never has to spell it correctly, only helpfully (the blog-post-URL pattern).

`next-handoff <id> [topic] [--label L]`: for `id ≠ 0000` the tool verifies a paired plan `{L}-{id}-*.md` exists in `changes/`/`debugging/` and refuses otherwise (no orphan handoffs); `0000` skips that check. `path handoff <id>` lists `{L}-{id}[a-z]*` in letter order. (The first argument is always the slice id here; the old "non-numeric first arg means topic" overload is dropped now that `--label` carries the effort — `topic` is simply the optional second positional.)

`next-note` (questions) and `next-report` (reports) don't touch the counter or an effort: `YYYY-MM-DD-{slug}.md` (today's UTC date) and `{slug}.md` respectively.

## Scaffolding: what the tool fills vs. what the agent fills

"Scaffold the file" means the tool **creates** it with everything deterministic already filled, leaving only prose and judgment for the agent.

| Kind | Template | Tool fills (deterministic) | Agent fills (judgment) |
|---|---|---|---|
| `changes/`, `debugging/` | `skills/plan-template.md` | `status: planned`; `created`/`updated` = now UTC ISO (quoted); `label: L` | title, problem/scope/approach/criteria, `editable_repos` (the subset of the effort's repos this slice touches) |
| `handoffs/` | minimal stub | heading `# {L}-{NNNN}{letter} handoff` (+ topic if given); `Date:` = now UTC; a `Spec:` pointer to the paired plan (omitted for `0000`) | the handoff prompt body |
| `questions/` | minimal stub | heading + `Date:`; empty `## Question` / `## Answer` / `## Sources` | the Q&A content |
| `reports/` | **new** `skills/report-template.md` | frontmatter `title` (from slug), `status: living`, `current_as_of`, `created`/`updated`, empty `related:` | the synthesis body, `destined_for:` |

The slice frontmatter no longer carries `branch_prefix`, `implementation_branch`, or `implementation_base` — `label` replaces the first, and the branch/base live in the effort registry (per repo), so the tool fills `label` and the agent fills only `editable_repos` (a name list). `next-debugging` reuses `plan-template.md` deliberately: debugging notes are plan-*shaped* in practice (full plan frontmatter + `## Plan`/`## Outcome`), so one template fits both; the `plan-and-implement.md` "save the trace" wording is nudged to match.

The tool **never** fills a judgment field with a guess. `implementation_base` is the one field this rewrite *does* fill — but only because `effort new`/`set-branch` compute it from real git state (merge-base against the atlas ref), never inferred.

Follow-on artifacts:

- **Add `report-template.md`** to `templates/skills/` (and have `install_skills_into_workspace` / `create_workspace` copy it). No new `package-data` entry needed — the existing `templates/skills/*.md` glob bundles it. Its frontmatter mirrors the `reports/` charter field-for-field (`title`/`status`/`current_as_of`/`created`/`updated`/`related`/`destined_for`).
- The handoff/question stubs live as inline strings in `cli.py` (headers, not structured documents).

(The earlier `package-data` bug — the global-skills glob omitting `upgrade-zentaizo.md` from built wheels — was fixed independently and has already landed; nothing to do here.)

## Flags and exit codes

- Compute-without-writing is `zentaizo path … --next`, not a `--dry-run` flag — one read verb, one write verb per concept.
- `--json` (on `effort`, `path`, and `next-*`) — structured output for agents that prefer parsing. For `next-*`/`path slice`: `{"path","kind","label","counter","created","wrote":bool}`. For `effort show`/`list`: the effort object(s) including the `repos` map. Aligns with the agent-facing-verb instinct in `ideas-worth-borrowing.md` §4.
- Exit `0` success, `2` not-found (`path`) / unknown-or-closed effort / taken label (`effort new`) / missing paired plan, `1` usage error. Errors → stderr; path(s) → stdout, so `$(zentaizo path slice 1)` and `$(zentaizo next-change …)` are safe to capture.
- Creators refuse to overwrite: if the composed path exists, exit 2. The final write uses exclusive-create semantics so a same-instant double-run loses cleanly rather than truncating.

## The payoff: what shrinks in `AGENTS.md`

`workspace_agents()` § Filename Convention today renders ~50 lines of procedure (the `derive_prefix` Python block, the "Finding the next counter value" shell snippet, the "Plan-creation collision check" steps, the "Parallel-agent safety" note). After this lands, that collapses to roughly:

> Work is grouped into **efforts** (a named body of work that may span several editable repos). Start one with `zentaizo effort new <word> --describe "…" --repo <name>=<branch>`; it reserves the name, records which repos/branches the effort uses, and becomes current. Session files are then allocated by the CLI: `zentaizo next-change <slug>` for a plan, `zentaizo next-debugging <slug>` for a debugging note, `zentaizo next-handoff <id> [topic]` for a handoff, `zentaizo next-note`/`next-report` for the rest — all default to the current effort (`--label` to override). To read, `zentaizo path slice <id>` / `zentaizo path active`, and `zentaizo effort show` for the effort's repos/branches. The commands allocate the shared counter and scaffold correct frontmatter.
>
> (Slice names look like `<label>-NNNN-<slug>.md`, so existing files read at a glance. If `zentaizo` is not on your PATH, install it — see the README — rather than naming a file by hand.)

The deterministic logic now has **exactly one home** (the code); the prose keeps a one-line shape *descriptor* and an install pointer — no allocation/lookup *procedure*, and **no branch→prefix algorithm at all**. The model is asked to *invoke*, never to *replay*.

### Every instruction touchpoint that must change

The CLI is only "aligned" if *all* prose that hand-composes a path or describes allocation/lookup is updated in lockstep. Complete inventory:

**AGENTS.md (`workspace_agents()`):**
- § **Filename Convention** — drop `derive_prefix`, the counter snippet, the collision-check steps, the parallel-agent prose; introduce the effort concept; keep a one-line shape descriptor + install pointer.
- § **Active Implementation Branches** → § **Active Efforts** — the source of truth for which work is live becomes the registry + `effort list`/`effort show`/`path active`, not the checked-out branch. Keep *why* (the atlas `ref` stays pinned to the durable default; effort state is conveyed by the registry + plan frontmatter, not atlas mutation). Note that an effort can span several editable repos on differently-named branches.
- § **Recording Work charters** — the `changes/`/`debugging/`/`handoffs/` charters reference the effort label + "the CLI allocates/scaffolds this" (the `handoffs/` charter also drops the superseded `<role>` scheme); `reports/`/`questions/` charters keep their topical/dated naming.
- § **From Brainstorming to Plan** — point at `effort new` (start/identify the effort) + `next-change` / `next-handoff` instead of hand-composed paths.

**`skills/plan-and-implement.md`:**
- **Pre-flight** — add "identify the effort with `zentaizo effort list`/`effort show`, or start one with `zentaizo effort new` (name it, describe it, register its repos/branches)"; the "check related prior plans" step → `zentaizo effort show` / `zentaizo path`.
- **Drafting step 1** (hand-composes the path + reads derivation/counter/collision rules) → `zentaizo next-change`.
- **Drafting step 2** (`status`/`created`/`updated`/`branch_prefix`) → CLI-filled; shrink to "fill `editable_repos` (the subset of the effort's repos this slice touches) + the body." Drop the `implementation_branch`/`implementation_base` instructions (registry-owned, computed by `effort new`/`set-branch`).
- **Handing off** section → `zentaizo next-handoff <id> [topic]`.
- **Executing step 4** → `next-note` / `next-debugging`.
- The "save the trace" wording → nudge to acknowledge debugging notes are plan-shaped.

**Generated README (`workspace_readme()`):** steps 5 & 6 hand-compose every session path → point at `effort` + the create verbs; mention multi-repo efforts.

**`skills/plan-template.md`:** new frontmatter (`label:` replaces `branch_prefix`; drop the `implementation_*` block); add a comment marking it a **CLI-consumed contract** (the scaffolder string-replaces `created:`/`label:`/`status:`).

**`templates/global-skills/zentaizo/`:** `SKILL.md` lists the new `effort`/`path`/`next-*` verbs alongside `validate`/`status`/`fetch`; `upgrade-zentaizo.md` knows the convention is now CLI-backed and that bringing a workspace forward includes a one-time migration: build `sessions/efforts.json` from existing `<prefix>-NNNN-*` files (each distinct prefix becomes an effort; map it to the repos/branches it used) and rename existing handoffs to the letter scheme.

Build-order step 5 executes this inventory as one commit, after the commands exist, so the instructions never describe a tool that isn't there yet.

## Implementation notes

- **One resolver core, thin command layers.** A pure `resolve_session_path(workspace, kind, *, id=None, slug=None, label=None, want_next=False, active=False) -> ResolveResult` does all naming/lookup against the registry + `sessions/`. `path_*` prints; the `next_*` creators call it with `want_next=True` then write the template; the `effort_*` commands read/write the registry. All register as subparsers with the standard `workspace` positional (`nargs="?", default="."`).
- **Registry helpers:** `load_efforts(workspace) -> dict` (read `sessions/efforts.json`, synthesizing a `main` effort + filesystem-reserved labels if absent), `save_efforts(workspace, data)`, `resolve_effort(workspace, label=None) -> dict` (label or `current`; raise on unknown/closed), `reserve_label(workspace, label)` (uniqueness against registry + filesystem), `compute_base(workspace, repo, branch)` (merge-base against atlas `ref` via `try_run_git`).
- **Resolver helpers:** `read_frontmatter(path) -> dict` (line scanner), `scan_slices(workspace, label) -> list[int]`, `find_slice_file(workspace, label, id) -> Path|None`, `find_active_plan(workspace, label) -> Path|None`, `next_handoff_letter(workspace, label, id) -> str`.
- These commands work before an atlas exists (a fresh workspace has `sessions/` but no atlas), so they gate only on `sessions/` existing — `compute_base` degrades to `null` when the atlas/repo is absent rather than failing.
- `report-template.md` copied by `install_skills_into_workspace` / `create_workspace`; `create_workspace` also writes the seed `sessions/efforts.json`.
- Reuse `try_run_git`, `read_json`/`write_json`, `utc_now`, `find_atlas`, `load_workspace`.

## Edge cases and non-goals

- **Same-effort concurrency** is not solved — two agents on the same effort can both compute `NNNN+1`. The exclusive-create on the final write makes a same-instant collision fail cleanly, but the counter race is inherent and out of scope (operational discipline: one agent per effort at a time; git worktrees as the escape hatch). The registry is a low-frequency file (untouched by slice creation), so it is not a concurrency hotspot.
- **No git dependency for naming.** Detached HEAD / no git / bare workspace are no longer special cases — labels do not derive from git. Git is consulted only to compute `base`, and its absence degrades to `null`, never a refusal.
- **Label / slug normalization (one rule).** Both the label and slugs land in paths the tool writes, so normalization is pinned, not best-effort: lowercase to ASCII; replace every run of non-`[a-z0-9]` with a single `-`; strip leading/trailing `-`. Then **reject** (usage error, exit 1) if the result is empty, or if the *original* contained a path separator (`/`/`\`), `..`, or a leading `.`. The tool normalizes but never *invents* a label or slug; a missing/empty one is a usage error.
- **Reserved `main`.** `main` is the default workspace-meta effort; it is pre-seeded and always available. It is a normal effort otherwise (it can have slices, `effort show main` works), it just isn't allocated from the themed list.
- **Not a migration tool.** Renaming existing branch-prefix files and building the registry for a pre-existing workspace is the `upgrade-zentaizo` skill's job.

## Testing

Unit tests (extend `tests/test_cli.py`):

- **Registry / `effort`:** `effort new` reserves a label and sets `current`; refuses a label already in the registry **and** one already used by an existing `<label>-NNNN-*` file (exit 2, no write); themed-word fallback is deterministic (1st → `sushi`, 2nd → `tempura`, skipping any taken); `--repo NAME=BRANCH` records the branch and computes `base` from a fixture repo (merge-base against the atlas ref); `set-branch` updates it; `switch` repoints `current`; `effort show`/`list` reflect state; `close` flips status and `next-change` then refuses the closed current effort.
- **Resolver:** `path slice <id>` recovers the on-disk slug; bare `43` and padded `0043` resolve identically; out-of-range/non-numeric id → exit 1; missing id → exit 2; two files sharing an id across `changes/`+`debugging/` (corrupt) → exit 2 listing both; `path slice --next` prints the next stem **and writes nothing** (assert the dir is unchanged); `path active` picks the highest-counter `changes/` plan whose `status` is not `done`/`superseded`/`abandoned`, ignores other labels and `debugging/`, exits 2 when all are closed.
- **Slug/label:** `"Token Rotation"` → `token-rotation`; a value containing `/`, `..`, or a leading `.` → exit 1 (no file written).
- **Creators:** `--json` shape; shared counter — `next-change` then `next-debugging` lands on the next number across both dirs; `next-handoff <id>` allocates `a` then `b`; lowercase-only letters; `next-handoff <id>` for `id ≠ 0000` refuses without a paired plan, `0000` does not; scaffolded frontmatter has a quoted UTC timestamp and correct `label`; refuse-to-overwrite.
- **Round-trip:** `effort new dojo` → `path slice --next` = `dojo-0001` → `next-change` → `path slice --next` = `dojo-0002` → `next-debugging` lands on `dojo-0002` → `path slice 2` resolves the file just created in `debugging/`.
- **Defaults:** with no `--label`, `next-change`/`path` use `current`; switching efforts changes the resolved label.

## Build order

1. Registry core + helpers (`load_efforts`/`save_efforts`/`resolve_effort`/`reserve_label`/`compute_base`) and the resolver helpers, with unit tests (I/O limited to `sessions/` + the registry + read-only git).
2. `zentaizo effort` group (`new`, `switch`, `show`, `list`, `set-branch`, `close`) + `--json`. Lands first: it is the new primitive everything else keys on, and `effort show`/`list` are independently useful read verbs.
3. `zentaizo path` (read-only) over the resolver: `slice <id>`, `slice --next`, `active`, `handoff`; `--json`.
4. `next-change` + `next-debugging` (shared counter, scaffold from `plan-template.md`) — the highest-value creators; ship and dogfood before the rest.
5. `report-template.md` + `next-report`; `next-handoff` (letter allocation, `0000`, paired-plan check); `next-note`. Pre-seed `sessions/efforts.json` in `create_workspace`.
6. Execute the **full instruction-touchpoint inventory** as one commit, after the commands exist (AGENTS.md §§ Filename Convention → effort, Active Implementation Branches → Active Efforts, Recording Work charters, From Brainstorming; all `plan-and-implement.md` steps; the generated README; the `plan-template.md` contract comment + `label:` frontmatter; `SKILL.md` + `upgrade-zentaizo.md`). Update tests that assert the old prose.

## Related

- `api-reference-docs-layer.md` — the deterministic-CLI / judgment-AI split this follows.
- `ideas-worth-borrowing.md` §4 ("an explicit agent-facing retrieval verb") — sibling thin verb; `--json` here and a future `zentaizo get`/`search` should share an output convention. `effort show` is itself a first agent-facing read verb.
- `edit-vs-reference-roles.md` — the `role: edit`/`reference` split; an effort's `repos` map only ever references `role: edit` repos.
- `zen-segmend-mesher-template-integration-round-2.md` — where this idea was first captured as deferred (and the source of the `main`/`mcgpu` effort examples).
