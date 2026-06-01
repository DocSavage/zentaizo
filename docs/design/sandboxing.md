# Sandboxing agentic execution in a Zentaizo workspace

_Design doc. Drafted 2026-05-30; revised 2026-05-31 after a Codex review (path-hardening, mode-based writable set, threat model split by enforcement class, concrete renderer contracts, a neutral `policy` output)._

_**Status (2026-05-31): build-order steps 1–4 are implemented and committed** — `compute_policy` (hardened), `zentaizo sandbox --target policy`, `--target claude` (merge + `--check`), and the README Core-Idea promotion, with 21 unit tests. **Steps 5–6 remain**: `--target codex` / `--target gemini` (need each harness's exact sandbox-config schema pinned first) and the separate `zentaizo-containers` repo. The per-step status is marked inline in [Build order](#build-order)._

## Problem

Agents are run **at the workspace level** (e.g. `~/work/zen-segmend-mesher`), not at the level of an individual editable repo — because the value of the workspace is precisely that the agent can see *all* the associated repos, the summaries, and the `sessions/` trail at once. But "see all of it" should not mean "write all of it." The access an agent actually needs is narrow:

- **write** its own `sessions/` (plans, outcomes, debugging, handoffs, reports, the effort registry) and `summaries/`, plus the **editable** repos;
- **read** everything else in the workspace — crucially the **reference** repos, whose entire purpose is to be read;
- **touch nothing outside** the workspace.

Today that policy is enforced ad hoc and per harness. The maintainer grants Codex more autonomy at the workspace level so it can file and update plans; Claude is run in auto mode with no clean way to confine it to "sessions/ + editable repos, reference repos read-only." Each harness has its own knobs, and getting it wrong means either too little autonomy (constant prompts) or too much (an agent rewriting a reference repo, or escaping the workspace).

## The key insight: the atlas already encodes the policy

Zentaizo does not need to *invent* the access policy — it is a restatement of the `role: edit` / `role: reference` split the atlas already carries, plus the workspace boundary. The policy has a **mode**, because two kinds of agent want two different writable sets:

```
mode = implement   (the default — an agent editing code)
  writable  = sessions/ , summaries/ , tmp/ , repos/<each role:"edit" repo>
  read-only = repos/<each role:"reference" repo>
            + the workspace's own owned files: zentaizo.atlas.json,
              zentaizo.lock.json, skills/, AGENTS.md, README.md, CLAUDE.md, GEMINI.md
  denied    = everything outside the workspace root

mode = curate   (an agent running curate-atlas / upgrade-zentaizo)
  writable  = the implement set + the owned files above
  read-only = repos/<each role:"reference" repo>
  denied    = everything outside the workspace root
```

The mode split resolves a real tension flagged in review: an *implementing* agent should not be able to rewrite the atlas, the lock, or the conventions it is working under — those are the source of truth, and a silent edit to them is exactly the drift the workspace exists to prevent — whereas a *curation* agent's whole job is to edit them. Default to `implement`; opt into `curate` for atlas/convention work. (`sessions/efforts.json` lives under `sessions/`, so the effort registry stays writable in both modes.)

So **Zentaizo owns the *policy* (derived from the atlas + mode); the open problem is *enforcement*, and enforcement is where it goes harness-specific.** This is the same shape as the rest of Zentaizo: the atlas is the single source of truth, and a thin deterministic step renders it into something concrete (here, per-harness guardrails or container mounts) — the same way the atlas already drives `fetch` behavior.

`compute_policy(workspace, mode="implement") -> {writable: [...], readonly: [...], deny_outside: bool}` is one pure function over the atlas. **Step zero is path-hardening, not rule generation**: every writable / read-only entry is built from a repo `name` string in the atlas, so before any rule is emitted the name is rejected if it is absolute, contains a path separator or `..`, begins with `.`, or — once resolved, following symlinks — escapes the workspace root; duplicate repo names (which would otherwise drop one path into *both* the writable and read-only sets) are rejected too. A sandbox policy that trusts unsanitized atlas strings is worse than none, so this guard precedes everything. Everything below consumes the hardened output.

## Three enforcement layers

Increasing strength, increasing cost. They are complementary, not alternatives.

### Layer 1 — Harness-native config (no container, best-effort)

Each harness can be told the policy through its own config. This is the cheapest and solves the day-to-day need, but it is **best-effort**: file-tool deny rules do not stop a shell redirect (see Threat model), so a determined or careless `Bash` command can still write where the file tools cannot.

- **Claude Code** — `.claude/settings.json` `permissions.deny` with path globs, e.g. `Edit(repos/<ref>/**)` and `Write(repos/<ref>/**)` for every reference repo (and, under `implement` mode, the workspace's owned meta files). `deny` takes precedence over `allow`, and is honored in **auto-accept-edits** mode (the mode the maintainer wants). The trap: `--dangerously-skip-permissions` (full bypass) ignores `deny`, so the recipe is *auto-accept-edits + deny rules*, never bypass. Reads are already confined to the project root unless `additionalDirectories` is set, so the workspace boundary mostly comes for free. Note a glob can't express "all repos except the editable one" (deny beats allow), so the reference repos are enumerated explicitly — exactly the kind of list a tool should generate, not a human maintain.
- **Codex CLI** — already ships an OS-level sandbox (Landlock/seccomp on Linux, Seatbelt on macOS) with `read-only` / `workspace-write` / `danger-full-access` modes and configurable writable roots. `workspace-write` confines writes to the workspace; setting the writable roots to `sessions/`, `summaries/`, and the editable repos approximates the policy, leaving reference repos read-only.
- **Gemini CLI** — has a `--sandbox` (Docker/Podman, or macOS Seatbelt) and approval modes, with less granular per-path control; the container path (Layer 3) is the natural fit.

### Layer 2 — `zentaizo sandbox` (core CLI, stdlib, no new deps)

Generalize Layer 1 into one command that renders `compute_policy()` into each harness's native config:

```
zentaizo sandbox --target policy    # print compute_policy() as JSON (no side effects)
zentaizo sandbox --target claude    # emit/update .claude/settings.json deny rules
zentaizo sandbox --target codex     # emit Codex sandbox config (writable roots)
zentaizo sandbox --target gemini    # emit the Gemini equivalent
```

`--target policy` is the **neutral backend**: it renders nothing harness-specific, just prints the hardened policy. It is the golden output the unit tests assert against and the shared contract `zentaizo-containers` consumes, which is why it lands before any harness renderer. `--mode implement|curate` selects the writable set; `--check` renders without writing and exits nonzero on drift (for a `git`-style "is the committed config still in sync with the atlas?" check).

It is pure text generation from the atlas — no runtime, no new dependencies — so it lives in the thin core alongside `validate`/`fetch`/`effort`. It refreshes the config when the atlas changes (a repo's role flips, a repo is added), so the guardrails never drift from the source of truth. This is the everyday default: it makes the common harnesses behave without asking the maintainer to hand-maintain permission lists.

### Layer 3 — `zentaizo-containers` (separate allied repo, opt-in, heavier deps)

The only **airtight, model-agnostic** enforcement: launch the chosen harness inside a container with the workspace bind-mounted *per policy* — reference repos `:ro`, `sessions/` + editable repos `:rw`, nothing else mounted at all. The OS enforces it regardless of what the agent or its shell attempts, closing the Bash-escape hole that defeats Layer 1. Per-harness images differ (each tool containerizes differently), but every image consumes the *same* `compute_policy()` output as its mount map.

This belongs in a **separate repo**, not the `zentaizo` package, to keep Docker/Podman and per-harness images out of the core's `dependencies = []` — the same opt-in-extra discipline as the `[docs-scan]` feature. The core stays installable and thin; the heavy isolation machinery is opt-in for when an airtight guarantee is actually wanted.

## Architecture

```
                      atlas (role: edit / reference)
                                  │
                        compute_policy(workspace)
                                  │
              ┌───────────────────┼───────────────────────┐
   zentaizo sandbox --target X    │              zentaizo-containers
   (renders harness config)       │              (renders mount map per harness)
   Layer 1/2, best-effort         │              Layer 3, airtight
```

One policy, two rendering backends. The policy is the durable thing; the backends are adapters that will change as the harnesses change.

## Renderer contracts

Each `--target` is an adapter with a fixed, testable contract — what file it owns, how it merges with an existing one, how its own entries are recognized on the next run, and how drift is reported.

- **`policy`** — writes nothing. Prints the `compute_policy()` object as indented JSON to stdout: `{version, mode, workspace (absolute), writable[], readonly[], deny_outside}`, every path list workspace-relative POSIX and sorted. This is the contract every other backend (and `zentaizo-containers`) reads.
- **`claude`** — owns `<workspace>/.claude/settings.json`. Merge, not clobber: an existing file is loaded and all keys preserved; under `permissions.deny`, zentaizo manages only the entries it recognizes as its own — `Edit(<p>/**)` / `Write(<p>/**)` where `<p>` is a `repos/<name>` path or one of the workspace-owned meta files — dropping the previous managed set (so a removed or role-flipped repo's stale rule disappears) and re-adding the freshly computed one. Deny entries for any *other* path, and all `allow`/`ask` rules, are left untouched. The renderer also denies `Edit(.claude/**)` / `Write(.claude/**)` so the agent cannot edit away its own guardrails. Output is sorted and stable, so re-running on an unchanged atlas is a byte-for-byte no-op; `--check` reports `up to date` / `drift` and sets the exit code without writing. Because zentaizo owns the `repos/*` and meta deny entries, a hand-added deny for *those* paths is replaced on the next render — within a workspace, repo write policy is zentaizo's to own, by design.
- **`codex` / `gemini`** *(planned)* — Codex consumes the same policy as its `workspace-write` writable roots; Gemini's coarser per-path control points at the container (Layer 3). Their contracts are pinned when implemented.

## Threat model: what each enforcement class actually constrains

The three layers are not one guardrail at three strengths — they are three *classes* of enforcement, and conflating them is the mistake to avoid. The deny globs Claude reads are not the same kind of thing as an OS sandbox, so the honest statement is per target, not blanket "Layer 1/2 = file tools."

| Enforcement class | Examples | Constrains the shell (`Bash`)? | Escape |
|---|---|---|---|
| **File-tool guardrail** | Claude `permissions.deny` globs | **No** — only the Edit/Write tools | a `Bash` redirect (`echo … > repos/<ref>/x`), `git -C repos/<ref> …`, `sed -i`, etc. slips past |
| **OS sandbox** | Codex Landlock/seccomp (`workspace-write`), Gemini Seatbelt | **Yes** — the kernel mediates every write the process makes, shell included | bounded by the sandbox's own coverage (e.g. a writable root that is too broad), not by tool-vs-shell |
| **Container** | `zentaizo-containers` bind-mounts (`:ro` / `:rw`) | **Yes** — the kernel enforces the mount table and the shell is inside the jail | only a container-runtime / kernel escape |

The consequence for `zentaizo sandbox`:

- The **`claude` target is a file-tool guardrail**: cheap, no deps, catches the overwhelming majority of *accidental* writes (the agent's own edit tools reaching for a reference repo), but a determined or careless `Bash` command writes around it. Sell it as a guardrail, never as a boundary.
- The **`codex` target renders into a real OS sandbox** Codex already ships, so it *does* constrain the shell — a stronger guarantee than the Claude target, but only as tight as the writable roots it is handed, and still not a substitute for a container when the source material is untrusted.
- The **container (Layer 3) is the only airtight, model-agnostic boundary**, because the kernel — not the agent, and not the harness's own honor system — enforces the mounts.

Stating the class honestly per target matters: `zentaizo sandbox --target claude` and `--target codex` are *not* the same promise. Neither file-tool nor (necessarily) OS-sandbox layers should be sold as a security boundary; the boundary is the container.

## Trade-off: container ergonomics

Containers are the strong option but change the *ergonomics*: the harness runs inside the container, so IDE integration, credential/auth flow, and `git push` from inside all need a per-harness answer. That cost is itself the argument for the layered design — Layer 2 (`zentaizo sandbox`) as the frictionless everyday default, Layer 3 (`zentaizo-containers`) reserved for when the guarantee is worth the ergonomic tax (untrusted source material, a long autonomous run, a shared machine).

## Relation to Core Ideas

This realizes the **least-privilege, sandboxable execution** idea — the "edit/reference drives sandbox isolation" point from the original README Core Ideas that was lost in a compression pass. It is now the sixth README Core Idea (promoted once `zentaizo sandbox` existed to support it):

> **Least-privilege, sandboxable execution** — an agent gets the narrowest access that lets it work: write its own `sessions/` and the editable repos, read everything else, touch nothing outside the workspace.

with **edit/reference**, **`zentaizo sandbox`**, and **`zentaizo-containers`** tagged as its mechanisms (the first two shipped; the container is pending). The principle ships together with a concrete mechanism that serves it rather than as an aspiration.

## Non-goals

- **Not a security product.** The file-tool target (`claude`) is a guardrail against accidents and drift, not a sandbox-escape boundary; the OS-sandbox target (`codex`) is stronger but only as tight as its writable roots. The container is the only boundary.
- **No new core dependencies.** `zentaizo sandbox` is stdlib text generation; everything that needs a container runtime lives in `zentaizo-containers`.
- **Not auto-launching agents.** Zentaizo renders policy into config/mounts; it does not wrap or supervise the agent process (that is `zentaizo-containers`' job, if anything).
- **Atlas stays the source of truth.** Sandboxing reads the atlas; it never mutates roles or invents a policy the atlas doesn't express.

## Build order

Revised after review so the hardened policy and a neutral golden output land before any harness renderer. Steps 1–4 are done (committed 2026-05-31); 5–6 remain.

1. **✅ Done — Hardened `compute_policy(workspace, mode)`** over the atlas — path-safety *first* (reject absolute / `..` / separator / dotfile / symlink-escape repo names and duplicate names), then the writable / read-only / deny-outside sets per mode. Unit-tested heavily *before* any renderer: explicit and omitted roles (omitted ⇒ reference), invalid role, missing atlas, not-yet-fetched repos, a symlinked repo dir that escapes the workspace, path-traversal names, duplicate names, both modes, and that the output is sorted and stable. *(in `src/zentaizo/cli.py`; tests in `tests/test_cli.py::SandboxPolicyTests`.)*
2. **✅ Done — `zentaizo sandbox --target policy`** — the neutral JSON backend, the golden output the tests assert against and the contract `zentaizo-containers` will read. *(the default target; no side effects.)*
3. **✅ Done — `zentaizo sandbox --target claude`** — render/merge `.claude/settings.json` deny rules (merge with an existing file, recognize and replace only zentaizo-managed entries, `--check` for drift). The highest-value target — it solves the auto-mode confinement need today — and the simplest to validate against (2). *(tests in `SandboxRenderTests`.)*
4. **✅ Done — Promoted *Least-privilege, sandboxable execution* to a README Core Idea**, now that a mechanism (`zentaizo sandbox`) supports it.
5. **⬜ Pending — `zentaizo sandbox --target codex` / `--target gemini`** — render the OS-sandbox writable roots / Gemini equivalent from the same policy. Blocked on pinning each harness's exact sandbox-config schema (Codex `config.toml` `workspace-write` writable roots; the Gemini equivalent) before rendering.
6. **⬜ Pending — `zentaizo-containers`** (separate repo): per-harness images + a launcher that mounts the workspace per `compute_policy()`.

## Related

- `edit-vs-reference-roles.md` — the role split this policy is derived from; the original home of "the split also drives sandbox isolation."
- `api-reference-docs-layer.md` — the deterministic-CLI / judgment-AI split; `zentaizo sandbox` is squarely deterministic-CLI.
- `next-slice-cli-helper.md` — sibling "render the atlas/workspace state into something concrete" CLI; shares the thin-core, atlas-as-source-of-truth stance.
- `ideas-worth-borrowing.md` — the harness sandbox models (Claude permissions/devcontainer, Codex Landlock/seccomp, Gemini Docker) borrowed as Layer 1/3 enforcement.
