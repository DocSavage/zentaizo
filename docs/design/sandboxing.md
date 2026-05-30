# Sandboxing agentic execution in a Zentaizo workspace

_Design doc. Drafted 2026-05-30. Status: proposed (not yet implemented). Captures the direction agreed in discussion before `zentaizo sandbox` is built; `zentaizo-containers` follows it._

## Problem

Agents are run **at the workspace level** (e.g. `~/work/zen-segmend-mesher`), not at the level of an individual editable repo — because the value of the workspace is precisely that the agent can see *all* the associated repos, the summaries, and the `sessions/` trail at once. But "see all of it" should not mean "write all of it." The access an agent actually needs is narrow:

- **write** its own `sessions/` (plans, outcomes, debugging, handoffs, reports, the effort registry) and `summaries/`, plus the **editable** repos;
- **read** everything else in the workspace — crucially the **reference** repos, whose entire purpose is to be read;
- **touch nothing outside** the workspace.

Today that policy is enforced ad hoc and per harness. The maintainer grants Codex more autonomy at the workspace level so it can file and update plans; Claude is run in auto mode with no clean way to confine it to "sessions/ + editable repos, reference repos read-only." Each harness has its own knobs, and getting it wrong means either too little autonomy (constant prompts) or too much (an agent rewriting a reference repo, or escaping the workspace).

## The key insight: the atlas already encodes the policy

Zentaizo does not need to *invent* the access policy — it is a restatement of the `role: edit` / `role: reference` split the atlas already carries, plus the workspace boundary:

```
writable  = sessions/ , summaries/ , repos/<each role:"edit" repo>      (+ atlas/lock, the workspace's own meta files)
read-only = repos/<each role:"reference" repo>
denied    = everything outside the workspace root
```

So **Zentaizo owns the *policy* (derived from the atlas); the open problem is *enforcement*, and enforcement is where it goes harness-specific.** This is the same shape as the rest of Zentaizo: the atlas is the single source of truth, and a thin deterministic step renders it into something concrete (here, per-harness guardrails or container mounts) — the same way the atlas already drives `fetch` behavior.

`compute_policy(workspace) -> {writable: [...], readonly: [...], deny_outside: bool}` is one pure function over the atlas. Everything below consumes it.

## Three enforcement layers

Increasing strength, increasing cost. They are complementary, not alternatives.

### Layer 1 — Harness-native config (no container, best-effort)

Each harness can be told the policy through its own config. This is the cheapest and solves the day-to-day need, but it is **best-effort**: file-tool deny rules do not stop a shell redirect (see Threat model), so a determined or careless `Bash` command can still write where the file tools cannot.

- **Claude Code** — `.claude/settings.json` `permissions.deny` with path globs, e.g. `Edit(repos/<ref>/**)` and `Write(repos/<ref>/**)` for every reference repo. `deny` takes precedence over `allow`, and is honored in **auto-accept-edits** mode (the mode the maintainer wants). The trap: `--dangerously-skip-permissions` (full bypass) ignores `deny`, so the recipe is *auto-accept-edits + deny rules*, never bypass. Reads are already confined to the project root unless `additionalDirectories` is set, so the workspace boundary mostly comes for free. Note a glob can't express "all repos except the editable one" (deny beats allow), so the reference repos are enumerated explicitly — exactly the kind of list a tool should generate, not a human maintain.
- **Codex CLI** — already ships an OS-level sandbox (Landlock/seccomp on Linux, Seatbelt on macOS) with `read-only` / `workspace-write` / `danger-full-access` modes and configurable writable roots. `workspace-write` confines writes to the workspace; setting the writable roots to `sessions/`, `summaries/`, and the editable repos approximates the policy, leaving reference repos read-only.
- **Gemini CLI** — has a `--sandbox` (Docker/Podman, or macOS Seatbelt) and approval modes, with less granular per-path control; the container path (Layer 3) is the natural fit.

### Layer 2 — `zentaizo sandbox` (core CLI, stdlib, no new deps)

Generalize Layer 1 into one command that renders `compute_policy()` into each harness's native config:

```
zentaizo sandbox --target claude   # emit/update .claude/settings.json deny rules
zentaizo sandbox --target codex     # emit Codex sandbox config (writable roots)
zentaizo sandbox --target gemini     # emit the Gemini equivalent
```

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

## Threat model and the Bash escape

Layer 1/2 guardrails constrain the harness's **file tools** (Edit/Write). They do **not** reliably constrain `Bash`, because shell arguments aren't robustly path-matched and a redirect (`echo … > repos/<ref>/x`) or a `git -C repos/<ref> …` slips past a file-tool deny. Harness bash-sandbox features help but vary in coverage. So:

- Layer 1/2 is the right **default** (cheap, no deps, catches the overwhelming majority of accidental writes — the agent's own edit tools).
- Layer 3 (container) is the only layer that is **airtight**, because the kernel — not the agent — enforces the mount permissions, and the shell is inside the jail.

Stating this honestly matters: `zentaizo sandbox` should not be sold as a security boundary, only as a guardrail; the security boundary is the container.

## Trade-off: container ergonomics

Containers are the strong option but change the *ergonomics*: the harness runs inside the container, so IDE integration, credential/auth flow, and `git push` from inside all need a per-harness answer. That cost is itself the argument for the layered design — Layer 2 (`zentaizo sandbox`) as the frictionless everyday default, Layer 3 (`zentaizo-containers`) reserved for when the guarantee is worth the ergonomic tax (untrusted source material, a long autonomous run, a shared machine).

## Relation to Core Ideas

This realizes the **least-privilege, sandboxable execution** idea — the "edit/reference drives sandbox isolation" point from the original README Core Ideas that was lost in a compression pass. It is intended to become a sixth Core Idea once a mechanism exists to support it:

> **Least-privilege, sandboxable execution** — an agent gets the narrowest access that lets it work: write its own `sessions/` and the editable repos, read everything else, touch nothing outside the workspace.

with **edit/reference**, **`zentaizo sandbox`**, and **`zentaizo-containers`** tagged as its mechanisms. The Core Idea is deliberately *not* added to the README yet — it's added when `zentaizo sandbox` lands, so the principle ships together with at least one concrete mechanism that serves it rather than as an aspiration.

## Non-goals

- **Not a security product.** Layer 1/2 are guardrails against accidents and drift, not a sandbox escape boundary. The container is the boundary.
- **No new core dependencies.** `zentaizo sandbox` is stdlib text generation; everything that needs a container runtime lives in `zentaizo-containers`.
- **Not auto-launching agents.** Zentaizo renders policy into config/mounts; it does not wrap or supervise the agent process (that is `zentaizo-containers`' job, if anything).
- **Atlas stays the source of truth.** Sandboxing reads the atlas; it never mutates roles or invents a policy the atlas doesn't express.

## Build order

1. `compute_policy(workspace)` over the atlas (pure, unit-tested): writable / read-only / deny-outside.
2. `zentaizo sandbox --target claude` — render `.claude/settings.json` deny rules (merge with an existing file rather than clobber). The highest-value target (it solves the auto-mode confinement need today) and the simplest to validate.
3. `zentaizo sandbox --target codex` / `--target gemini`.
4. Promote **Least-privilege, sandboxable execution** to a README Core Idea, now that a mechanism (`zentaizo sandbox`) supports it.
5. `zentaizo-containers` (separate repo): per-harness images + a launcher that mounts the workspace per `compute_policy()`.

## Related

- `edit-vs-reference-roles.md` — the role split this policy is derived from; the original home of "the split also drives sandbox isolation."
- `api-reference-docs-layer.md` — the deterministic-CLI / judgment-AI split; `zentaizo sandbox` is squarely deterministic-CLI.
- `next-slice-cli-helper.md` — sibling "render the atlas/workspace state into something concrete" CLI; shares the thin-core, atlas-as-source-of-truth stance.
- `ideas-worth-borrowing.md` — the harness sandbox models (Claude permissions/devcontainer, Codex Landlock/seccomp, Gemini Docker) borrowed as Layer 1/3 enforcement.
