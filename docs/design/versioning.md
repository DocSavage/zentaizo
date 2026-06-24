# Versioning Policy

Zentaizo is pre-1.0 and uses `0.MINOR.PATCH` versions. It stays on `0.x` until the workspace format and CLI surface are deliberately declared stable. That declaration is the explicit `1.0.0` decision; it is never automatic.

Before `1.0.0`, each landed effort decides the increment:

- `MINOR`: the effort adds user-facing capability or changes the workspace format, CLI, or file conventions. This is the pre-1.0 stand-in for a breaking change.
- `PATCH`: the effort fixes behavior or changes internals without changing the user-facing surface.

The version bump happens at effort close. The closer reads the effort Outcome, classifies the effort as `MINOR` or `PATCH`, bumps the single source in `src/zentaizo/__init__.py`, and adds a `CHANGELOG.md` entry. One effort gets one bump, not one bump per slice.

Tag releases as `vMAJOR.MINOR.PATCH`. After `1.0.0`, switch to standard semantic versioning.
