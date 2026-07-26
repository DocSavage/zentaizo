# Versioning Policy

Zentaizo is pre-1.0 and uses `0.MINOR.PATCH` versions. It stays on `0.x` until the workspace format and CLI surface are deliberately declared stable. That declaration is the explicit `1.0.0` decision; it is never automatic.

Before `1.0.0`, each landed effort decides the increment:

- `MINOR`: the effort adds user-facing capability or changes the workspace format, CLI, or file conventions. This is the pre-1.0 stand-in for a breaking change.
- `PATCH`: the effort fixes behavior or changes internals without changing the user-facing surface.

The version bump happens at effort close. The closer reads the effort Outcome, classifies the effort as `MINOR` or `PATCH`, bumps the single source in `src/zentaizo/__init__.py`, and adds a `CHANGELOG.md` entry. One effort gets one bump, not one bump per slice.

The reserved `main` effort is the exception, because it never closes — `zentaizo effort close main` is refused by design. Work that lands on the trunk therefore bumps **per landed slice**: the slice's closeout reads its own Outcome, classifies it, bumps, and adds the changelog entry. Without that rule, trunk work would accumulate releases with no version at all. Consecutive docs-only slices landing together may share one `PATCH` bump whose changelog entry names each of them.

Workspace-facing changes also bump the conventions generation. Any release that changes generated workspace artifacts or session-file conventions — the same class of change this policy already calls `MINOR` — increments `CONVENTIONS_GENERATION` in `src/zentaizo/cli.py` and adds one concise `CONVENTIONS_DELTAS` entry describing what changed (the `upgrade-zentaizo` skill scopes its reconciliation by these entries, and `zentaizo status` prints them as "missed" lines). The `CHANGELOG.md` entry names the new generation. Behavior-only releases leave the generation alone so `zentaizo status` never over-reports workspace staleness.

After bumping, run `pixi update zentaizo` to sync the `pixi.lock` self-entry to the new version, and commit the lock with the bump. This works because `pyproject.toml` declares `[tool.uv] cache-keys` including `src/zentaizo/__init__.py` — the version is dynamic, and without that entry the resolver's cached metadata for the path package never invalidates on a bump, so the lock silently keeps the old version (the failure mode that preceded the `v0.10.0` release; if it recurs, the stale bucket lives under `~/.cache/rattler/cache/uv-cache/sdists-v9/path/`).

Tag releases as `vMAJOR.MINOR.PATCH`. After `1.0.0`, switch to standard semantic versioning.
