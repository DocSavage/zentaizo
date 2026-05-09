# Curate the Zentaizo Atlas

This procedure helps an LLM-driven coding tool (Claude Code, Codex CLI, Gemini CLI, Aider, etc.) interview the user and populate `zentaizo.atlas.json` — the human-curated list of repos, docs, papers, and notes that belong to one system.

The atlas is the heart of a Zentaizo workspace. A good atlas turns "go read this code" into "here is the whole landscape this code lives in." Spend the time to fill it in carefully; the rest of Zentaizo (fetch, summarize, provide-info) builds on it.

## When to run this procedure

Run it when:

- The atlas is empty (the user just ran `zentaizo create`).
- The user asks to "set up", "fill out", "populate", "extend", or "add to" the atlas.
- A new repo, doc, paper, or note has appeared in the system and should be tracked.
- The user is editing `zentaizo.atlas.json` and asks for help.

Do NOT run it for read-only questions like "what's in my atlas?" — for those, just read the file.

## Boundaries — what this procedure does NOT do

This procedure curates a list of *sources* that belong to one system. It does NOT record:

- **User preferences, coding style, or personal context.** Those belong in the host LLM's memory or rules file: `CLAUDE.md` / `MEMORY.md` for Claude Code, `GEMINI.md` for Gemini, `.codex/AGENTS.md` for Codex, `.aider.conf.yml` for Aider, and so on.
- **Project-wide conventions or build commands.** Those belong in `AGENTS.md` at the workspace root, or in the source repos themselves.
- **Generated summaries.** Those live under `summaries/` and are produced by `zentaizo summarize` plus a follow-up LLM pass.
- **Locked commit SHAs and snapshot metadata.** Those live in `zentaizo.lock.json`, written by `zentaizo fetch`. The atlas declares intent (a ref like `main` or `v1.2.0`); the lock records the resolution.

If the user mentions a fact that belongs in one of those other files, say so and let them decide where it lives. Do not silently merge it into the atlas.

## Pre-flight check

Before asking any questions:

1. Confirm `zentaizo.atlas.json` exists at the workspace root. If not, ask the user to run `zentaizo create` first, or to `cd` into an existing workspace.
2. Read the current atlas in full. The user may already have entries; the goal is to extend or refine, not re-interview from scratch.
3. Read `AGENTS.md` for any system-specific guidance the user already wrote.
4. If the atlas already has entries, summarize what's there in one sentence ("Your atlas already lists 3 repos, 1 doc, 0 papers, 0 notes") before asking what they want to change.

## The interview

Ask one question at a time. Wait for an answer. Do not pre-fill answers the user did not give. If the user is uncertain, offer concrete examples drawn from their stated system but mark them as suggestions.

### Step 1 — What system is this atlas about?

- Confirm or set `name` (defaults to the workspace directory name).
- Confirm or write a 1–3 sentence `description`. Aim for "what is this system, in a paragraph someone unfamiliar would understand". Not a marketing pitch, not a list of features.

### Step 2 — Central repos (typically 1–3)

Ask: "What is the primary code that makes this system run, or are we starting a greenfield project?"

- For each repo, collect: `name`, `url` (https or ssh), `ref` (see Step 7), `role` (see Step 2.5), and a 1-line `description`.
- "Central" means: editing it changes the system's behavior. Other code calls it, depends on it, or wraps it.
- Greenfield case: the user may not have a repo yet. That's fine — note the intent in the atlas description and revisit later.

### Step 2.5 — Edit or reference?

For each repo, ask: "Will the user edit this repo in this workspace, or read it for context?"

- **`role: "edit"`** — code that will be modified during this work. The atlas pins a starting `ref` (usually `main`); after the first fetch, the working tree is left alone so the user can branch and commit without `zentaizo fetch` clobbering progress.
- **`role: "reference"`** — code consulted but not changed. The atlas pins a `ref` (branch, tag, or commit); `zentaizo fetch` re-resolves the pin and refuses to overwrite a dirty working tree.

Default to `reference` when in doubt — the user can change it later. A typical multi-repo system has 1–3 edit repos and a longer tail of reference repos (clients, deployment, libraries you depend on). Repos without an explicit `role` are treated as `reference`.

### Step 3 — Supporting repos

Ask: "What other code does the system depend on or interact with?"

Examples to prompt the user:

- Client libraries (Python, JS, Go) consumers use to call the central service.
- Web frontends or admin UIs.
- Deployment configuration (Docker, Helm, Terraform, Kubernetes manifests).
- Scheduled jobs, cron tasks, lambdas.
- Dev tooling, testing harnesses, CI configuration.

### Step 4 — Public documentation

Ask: "Are there public docs or API references the assistant should be able to consult?"

- API references, vendor docs, public wikis, OpenAPI specs hosted on the web.
- Capture URL plus a 1-line description. Snapshot download is a future Zentaizo command — for now the URL alone is recorded.

### Step 5 — Papers and design docs

Ask: "Any papers, RFCs, or design docs that explain *why* the system is the way it is?"

- Specs, RFCs, academic papers, internal design docs (Google Docs, Notion, Confluence URLs).
- Skip if none. Better an empty list than padded entries.

### Step 6 — Internal notes

Ask: "Any postmortems, oncall traces, issue threads, or scratch findings the assistant should consult?"

- These often hold the load-bearing context for debugging — "we tried X in Q3, it didn't work because of Y."
- Skip if none.

### Step 7 — Picking ref values

Help the user pick a `ref` for each repo using this decision tree, considering its `role`:

- **For `role: "edit"` repos**: `ref` is the *starting point*. `main` is usually right; pin to a tag if you need a known-good base. After the first `zentaizo fetch`, your work diverges from the locked SHA by design — that's the whole point of an edit repo. `zentaizo fetch --rebase` can fast-forward a clean edit repo onto its current upstream.
- **For `role: "reference"` repos**: pick the strictness you want.
  - `main` (or the repo's default branch) for "always current"; the lock advances each `zentaizo fetch`.
  - A tag (`v1.2.0`) for "stable contract while a system evolves".
  - A commit SHA for "exact reproducibility".

When in doubt, default to `main`. The user can pin later.

### Step 8 — Description quality

Each entry's `description` should answer "why does this belong in the atlas?"

- Good: `"REST API for creating and resolving short links"`, `"client library used by scripts and integrations"`.
- Bad: `"the API repo"`, `"docs"`, `"important"`.

If a description is generic, ask the user for one more concrete sentence before saving.

## Writing the atlas

1. Show the user a unified diff of the proposed atlas changes before saving. Never save silently.
2. Preserve every existing entry the user did not modify. The interview extends; it doesn't overwrite.
3. Write the file as JSON with 2-space indent and a trailing newline (matching what `zentaizo create` produces).
4. Suggest the user commit the change with a meaningful message (e.g. `atlas: add deployment repo and design doc`).

## Validate and lock

After writing the atlas, walk the user through:

1. `zentaizo validate` — resolve any errors before fetching.
2. `zentaizo fetch` — clone or update repos and write `zentaizo.lock.json` with resolved commit SHAs.
3. (First-time setup) `zentaizo summarize` — emits a prompt; the user passes it back to their LLM tool to populate `summaries/`.

If `zentaizo validate` reports errors, fix them in the atlas (don't silently rewrite the user's URLs) and re-run.

## Re-invocation

If this procedure is run a second time on a workspace whose atlas is already populated, do not start over. Open with:

> "Your atlas already has N repos, M docs, P papers, Q notes. What would you like to change?"

Common follow-up tasks:

- Add a new source (skip Steps 1, 7's defaults; jump to the relevant Step 2–6).
- Update a `ref` (jump to Step 7).
- Improve descriptions (jump to Step 8).
- Remove a source no longer in the system.

Always show the diff before saving.
