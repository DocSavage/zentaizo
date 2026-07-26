# Sandboxed Agentic Execution

_Distilled design doc — current architecture + rationale._

## What it is

Agents run at the *workspace* level, not inside a single repo, because the value of a workspace is that the agent can see every associated repo, the summaries, and the `sessions/` trail at once. But "see all of it" must not mean "write all of it." The access an agent actually needs is narrow: write its own `sessions/` and `summaries/` plus the *editable* repos, read everything else (the *reference* repos especially), and touch nothing outside the workspace root. Zentaizo derives this least-privilege policy directly from the `role: edit` / `role: reference` split the atlas already carries — it does not invent a new access model — and renders it into a harness's native config. The policy is the durable artifact; the renderers are thin adapters that change as harnesses change.

## Architecture

The whole subsystem lives in `src/zentaizo/cli.py` (the sandbox section near `compute_policy`); content sanitization in `src/zentaizo/safety.py` is a separate fetch-time concern (see [Considered and not taken](#considered-and-not-taken)).

**`compute_policy(workspace, mode="implement")`** is one pure function over the atlas. It returns `{version, mode, workspace (absolute), writable[], readonly[], deny_outside}`, with every path list workspace-relative POSIX and sorted (so output is stable). Construction:

- Always-writable workspace dirs come from `SANDBOX_ALWAYS_WRITABLE` = `sessions`, `summaries`, `tmp`, the graph output dir (`graphify-out`), and `.graphifyignore` — the durable trail, local scratch, and the derived graph layer an implementing agent may rebuild mid-task.
- Each atlas repo is added to `writable` if its `repo_role(repo)` is `edit`, otherwise to `readonly` (reference is the default).
- The workspace's own owned files (`SANDBOX_OWNED_META` = the atlas, the lock, `skills`, `AGENTS.md`, `README.md`, `CLAUDE.md`, `GEMINI.md`) are read-only under `mode="implement"` and writable under `mode="curate"`. The two modes are listed in `SANDBOX_MODES`; an unknown mode is a hard error.
- `deny_outside` is always `True` — the workspace root is the outer boundary in every policy.

**Path-hardening is step zero.** Because each atlas repo `name` becomes a path the sandbox grants or denies, `_safe_repo_relpath(workspace, name)` screens it *before* any rule is emitted: it rejects an empty/non-string name, an absolute path, a leading `.`, any name containing a separator (`/` or `\`) or `..`, and — after resolving through symlinks — any name whose on-disk directory escapes the `repos/` root. `compute_policy` additionally rejects duplicate repo names (a duplicate could otherwise land one path in both the writable and read-only sets). A policy that trusted unsanitized atlas strings would be worse than none, so this guard precedes everything.

**`zentaizo sandbox`** (`sandbox_command`, parser in `_add_sandbox_parser`) renders the policy. Two targets are implemented:

- **`--target policy`** (the default) prints the `compute_policy()` object as indented JSON with no side effects. This is the neutral backend and the golden output the tests assert against.
- **`--target claude`** owns `<workspace>/.claude/settings.json`. `_render_claude_settings` merges rather than clobbers: it deep-copies the existing settings, preserves all `allow`/`ask` rules and any *non-managed* `deny` entries, drops the previous managed set (matched by `_MANAGED_DENY_RE`), and appends the freshly computed one. Managed entries are `Edit(<p>)` / `Write(<p>)` for each read-only path (`_claude_deny_globs` emits an exact match for `.md`/`.json` files and `<dir>/**` for directories) plus self-protecting `Edit(.claude/**)` / `Write(.claude/**)` so the agent cannot edit away its own guardrails. Because the result is sorted and stable, re-rendering an unchanged atlas is a byte-for-byte no-op. A malformed `settings.json`, a non-object `permissions`, or a non-list `permissions.deny` aborts rather than overwriting.

`--mode implement|curate` selects the writable set; `--check` (claude target) renders without writing and exits nonzero on drift, for a `git`-style "is the committed config still in sync with the atlas?" check. The command re-derives from the atlas every run, so guardrails never drift from the source of truth — a removed or role-flipped repo's stale rule disappears on the next render.

The honest scope of the `claude` target is a **file-tool guardrail**, not a security boundary: it constrains only the Edit/Write tools, so a `Bash` redirect or `git -C repos/<ref> …` writes around it. It catches accidental writes that arrive through the agent's edit tools, which is the common case for a reference repo touched by mistake, though no measurement backs a proportion and keeps the committed config in sync with the atlas — that is what it is sold as.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Where the policy comes from | Derive it from the atlas `role: edit`/`reference` split, never a separate config | The access policy is a restatement of a distinction the atlas already carries; a second source would drift |
| Policy vs enforcement | One pure `compute_policy()`; thin per-target renderers | Same shape as the rest of Zentaizo — atlas is the source of truth, a deterministic step renders it into something concrete |
| Path-hardening first | Screen every repo `name` (and reject duplicates) before emitting any rule | An atlas-supplied string becomes a grant/deny path; trusting it unsanitized is worse than no sandbox |
| Two modes | `implement` (default) makes owned meta read-only; `curate` makes it writable | An implementing agent must not silently rewrite the atlas/lock/conventions it works under; a curation agent's whole job is to edit them |
| Claude render is a merge | Own only `_MANAGED_DENY_RE` entries; preserve user `allow`/`ask`/other `deny` | Lets the maintainer keep hand-authored rules while zentaizo owns the `repos/*` and owned-meta denies |
| `--check` for drift | Render-and-compare, exit nonzero, no write | CI-style guard that the committed config still matches the atlas |
| Self-protection | Always deny `Edit/Write(.claude/**)` | The agent must not edit away its own guardrails |
| No new dependencies | `sandbox` is stdlib text generation in the thin core | Keeps the core installable and thin; heavier isolation is deferred |

## Considered and not taken

- **Codex / Gemini render targets.** The design anticipates a `--target codex` (rendering the OS-level `workspace-write` writable roots Codex already enforces) and a Gemini equivalent, but only `policy` and `claude` are implemented today; the `--target` choices are limited to those two.
- **Container-based enforcement (`zentaizo-containers`).** The only airtight, model-agnostic boundary is launching the harness inside a container with the workspace bind-mounted per policy (reference repos `:ro`, writable set `:rw`, nothing else mounted). This is deliberately a *separate, opt-in* repo so Docker/Podman and per-harness images stay out of the core's dependency set; the same `compute_policy()` output is its mount map. Not built yet.
- **Selling any rendered target as a security boundary.** The `claude` target is a file-tool guardrail and an OS-sandbox target would only be as tight as its writable roots; the container is the only real boundary. This is an explicit non-goal — zentaizo renders policy, it does not supervise or wrap the agent process.
- **Treating content sanitization as part of this subsystem.** `src/zentaizo/safety.py` screens *untrusted fetched content* (invisible-character stripping, injection-signature flagging) at fetch time. It is a distinct concern from confining where an agent may write and is not part of the sandbox policy.

## See also

- `src/zentaizo/cli.py` — `compute_policy`, `_safe_repo_relpath`, `sandbox_command`, `_render_claude_settings`, `_MANAGED_DENY_RE`, and the `SANDBOX_*` constants.
- `docs/design/foundations.md` — the `role: edit`/`reference` split this policy is derived from.
- `docs/workspace-format.md` — repo roles and the read-write / read-only intent.
- `docs/cli.md` — the `sandbox` command in the CLI reference.
