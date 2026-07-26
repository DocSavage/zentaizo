# Codex Goal Usage

Guidance for running long autonomous Codex sessions with `/goal` in this repo or
similar local projects.

## Recommended interactive setup

Use this when you want normal sandboxing, but still want Codex to be able to ask
for permission when Git metadata needs to be written:

```bash
codex -C /path/to/repo \
  --sandbox workspace-write \
  --ask-for-approval on-request
```

This keeps ordinary file edits sandboxed while allowing Codex to request a
one-off approval for operations such as `git add` or `git commit`, which must
write files under `.git/`.

In the `/goal` prompt, include:

```text
You may request approval for Git metadata writes needed to stage/commit.
Keep other work sandboxed. If a command fails due to sandbox permissions,
diagnose the exact blocker and either request approval or stop before doing
workaround churn.
```

## Autonomous with commit access

Use this when you want `--ask-for-approval never`, but still want Codex to be
able to stage and commit inside one dedicated repo:

```bash
codex -C /path/to/repo \
  --sandbox workspace-write \
  --ask-for-approval never \
  --add-dir /path/to/repo/.git
```

The intent is to keep worktree edits scoped to the repo while also making Git
metadata writable, so Git can create `.git/index.lock`, update the index, write
commit objects, and move branch refs. The `--add-dir` path should be the actual Git
directory for the checkout; in unusual worktree setups, use
`git rev-parse --absolute-git-dir` to find it.

**Verify this against your Codex build before relying on it.** Codex's documented
sandbox behavior protects `.git` recursively beneath a writable root, and its docs do
not resolve the case where `.git` itself is passed as an added root — so whether this
recipe grants write access is a property of the build you are running, not something
this page can promise. Test it on a throwaway commit first.

Use this only when the checkout is dedicated to the Codex session or you are
comfortable with normal Git lock behavior being the concurrency guard. It lets
Codex commit without prompts, so the `/goal` prompt should still tell Codex to
check `git status`, stage only intended files, and stop if unrelated changes
would make the commit ambiguous.

## Fully autonomous setup

Use this only in a disposable clone, VM, container, or other environment that is
already externally sandboxed:

```bash
codex -C /path/to/disposable-worktree \
  --sandbox danger-full-access \
  --ask-for-approval never
```

This is the least interruptive setup for long runs, but it removes Codex's
filesystem guardrails. Do not use it on a machine or in a checkout where broad
local access would be unsafe.

## Safe patch-only setup

Use this when you want maximum guardrails and do not need Codex to commit:

```bash
codex -C /path/to/repo \
  --sandbox workspace-write \
  --ask-for-approval never
```

In this mode, Codex can usually edit tracked and untracked worktree files, run
tests, and leave a verified patch. It may not be able to stage or commit,
because Git needs to create files such as `.git/index.lock`. If `.git` is
read-only in the active permission profile, commit completion is an environment
blocker, not a patch problem.

## Goal preflight

For long `/goal` runs, ask Codex to do this before implementation:

```text
Before implementing, run a preflight:
- read AGENTS.md/CLAUDE.md and task docs
- check git status and current branch
- verify .git is writable with a harmless staging/index-lock probe
- verify package/test commands
- confirm whether commits are expected
- if any required capability is blocked, report it before starting implementation
```

The important check is whether Codex can mutate Git metadata. Catching that
before implementation prevents a long run from ending with a verified patch that
cannot be committed inside the current session.

## Rule of thumb

- Want commits and occasional approvals: `workspace-write` plus `on-request`.
- Want commits with no approval prompts in a dedicated checkout:
  `workspace-write` plus `never` plus `--add-dir /path/to/repo/.git`.
- Want uninterrupted autonomous execution: disposable environment plus
  `danger-full-access` and `never`.
- Want maximum safety: `workspace-write` plus `never`, but ask Codex not to
  commit; it should leave a verified patch and exact commit commands.
