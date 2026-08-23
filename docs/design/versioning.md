# Versioning Policy

Zentaizo is pre-1.0 and uses `0.MINOR.PATCH` versions. It stays on `0.x` until the workspace format and CLI surface are deliberately declared stable. That declaration is the explicit `1.0.0` decision; it is never automatic.

Before `1.0.0`, each landed effort decides the increment:

- `MINOR`: the effort adds user-facing capability or changes the workspace format, CLI, or file conventions. This is the pre-1.0 stand-in for a breaking change.
- `PATCH`: the effort fixes behavior or changes internals without changing the user-facing surface.

The version bump happens at effort close. The closer reads the effort Outcome, classifies the effort as `MINOR` or `PATCH`, bumps the single source in `src/zentaizo/__init__.py`, and adds a `CHANGELOG.md` entry. One effort gets one bump, not one bump per slice.

The reserved `main` effort is the exception, because it never closes — `zentaizo effort close main` is refused by design. Work that lands on the trunk therefore bumps **per landed slice**: the slice's closeout reads its own Outcome, classifies it, bumps, and adds the changelog entry. Without that rule, trunk work would accumulate releases with no version at all. One *landing* gets one version, even when it carries several slices: when a run of slices lands together, collapse their bumps into the single highest increment and write one changelog entry covering them. Separate entries would name versions no one could ever install.

Workspace-facing changes also bump the conventions generation. Any release that changes generated workspace artifacts or session-file conventions — the same class of change this policy already calls `MINOR` — increments `CONVENTIONS_GENERATION` in `src/zentaizo/cli.py` and adds one concise `CONVENTIONS_DELTAS` entry describing what changed (the `upgrade-zentaizo` skill scopes its reconciliation by these entries, and `zentaizo status` prints them as "missed" lines). The `CHANGELOG.md` entry names the new generation. Behavior-only releases leave the generation alone so `zentaizo status` never over-reports workspace staleness.

After bumping, do not expect a `pixi.lock` self-entry diff. The v7 lock format no longer records the local path package's `version` field, so `pixi update zentaizo` has no version value to synchronize. Commit a lock change only when dependency resolution actually changes; never manufacture one to accompany the release bump. The `[tool.uv] cache-keys` entry for `src/zentaizo/__init__.py` remains useful to invalidate dynamic package metadata outside the v7 self-entry.

Tag releases as `vMAJOR.MINOR.PATCH`, following ordinary semantic-versioning practice: a tag marks a released version so it stays reachable later. The increment does not decide whether to tag — `PATCH` releases are tagged too. What decides it is whether the release changes something a user can observe: behavior, the CLI surface, or generated workspace text. A version that only rewords documentation or rearranges internals does not need a tag, because its `CHANGELOG.md` entry is already the record. Use an annotated tag (`git tag -a`) whose subject names what the release changed, matching `v0.15.0` and later. After `1.0.0`, switch to standard semantic versioning.
