# Design docs

Distilled, repo-scoped design docs — the current architecture of each subsystem
and the rationale behind it. The full before/after design *provenance* lives in
the development workspace's `sessions/` trail; these docs are the settled
distillate that ships with the repo.

- [foundations.md](foundations.md) — source roles (`edit`/`reference`), the
  atlas-vs-lock split + curation, and how workspace conventions feed back into
  the bundled templates.
- [docs-layer.md](docs-layer.md) — the reference-docs layer: sourcing,
  snapshotting, the fetch-time safety pass, and incremental focus-aware summaries.
- [session-model.md](session-model.md) — efforts, CLI-allocated slices/sessions,
  slice statuses, the handoff/restart loop, and the editor ledger.
- [claude-integration.md](claude-integration.md) — AI coding-harness glue: the
  session-title hook, the `AGENTS.md` import, and commit attribution.
- [integrations.md](integrations.md) — external knowledge integrations: the built
  `zentaizo graph` layer over Graphify (and the proposed, unimplemented Context
  Hub tier).
- [sandboxing.md](sandboxing.md) — sandboxed agentic execution: deriving a
  least-privilege policy from repo roles and rendering it into a harness's native
  config.
