# Documentation Style Guide

This guide fixes the register and the vocabulary of Zentaizo's own documentation. Anyone
editing prose in this repository — a person or an agent — applies it to the passages they
touch. Its purpose is narrow: a claim about Zentaizo's behavior should be checkable
against the code that implements it, and one concept should be named by one word on
every page.

## What this guide governs

**Governed:** the markdown prose in this repository — `README.md`, `docs/cli.md`,
`docs/workspace-format.md`, `docs/use-cases.md`, `docs/codex-goal-usage.md`,
`docs/design/*`, and this file.

**Not governed:**

- **`sessions/` prose in a workspace** — effort docs, slice plans, handoffs, reports,
  and Q&A logs. Those are a working record, not a published surface, and the
  templates that scaffold them are deliberately silent about register.
- **`CHANGELOG.md`** — it records history and is exempt from retroactive edits.
- **Generated workspace text** — the `AGENTS.md`, `README.md`, and `provide-info`
  block that `src/zentaizo/cli.py` writes into a workspace, and the files under
  `src/zentaizo/templates/`. The **register** rules do not reach it, because that text
  is code rather than prose. The **glossary does**: a concept is named the same way
  whether the words ship in a doc or in generated output. Correcting generated text is
  a conventions change under `docs/design/versioning.md` — a `CONVENTIONS_GENERATION`
  bump and a `CONVENTIONS_DELTAS` entry — so it lands as its own change rather than
  inside a documentation edit.
- **Fetched or vendored content** under `repos/`, `docs/`, `papers/`, and `notes/` in
  a workspace. That material is untrusted input to quote, not prose to edit.

## How to apply it

Apply the rules to every passage you write or edit. They are not a mandate to rewrite
compliant prose: an unnecessary edit to a sentence that already complies makes a diff
harder to review and is itself a defect.

Each rule is numbered within its group so that a review can cite one — "violates C2",
"heading fails D2". The groups are **S**entences, **P**aragraphs, **D**ocuments, diction
(**X**), and **C**laims. The claims group is the load-bearing one: a rule that
requires a cited implementation turns an unverifiable statement into one a reviewer can
check against the code.

## Sentences

- **S1.** Keep the verb within about seven words of its grammatical subject. Move long
  qualifiers to the start or the end of the sentence.
- **S2.** Express each clause's action as a verb, not as an abstract noun: "the CLI
  allocates every session filename", not "session filename allocation is handled by
  the CLI".
- **S3.** Default to active voice with a named actor. Use the passive only to hold an
  established topic in subject position, or when the actor is genuinely irrelevant.
- **S4.** Describe behavior in the present tense. Give instructions in the imperative.
- **S5.** Keep sentences at or under about 30 words — one main clause plus at most one
  subordinate clause.
- **S6.** Delete intensifiers: *very*, *really*, *simply*, *just*, *easily*,
  *powerful*, *seamless*, *blazing*. If a modifier carries information, replace it with
  a number or a named limit.

## Paragraphs

- **P1.** Open each sentence with the component, file, command, or person the sentence
  is about.
- **P2.** Put established information first and the point you want remembered at the
  end of the sentence.
- **P3.** Give the definition before the term that depends on it, and the problem
  before the mechanism that solves it.
- **P4.** Make one claim per paragraph.
- **P5.** In a list, keep items grammatically parallel and put each item's subject
  first. When a list defines terms, bold the term at the start of the item.

## Documents

- **D1.** The first two sentences of a page state what the thing does and who runs it.
- **D2.** Section headings (`##` and deeper) use sentence case, are grammatically
  parallel among siblings, and end without punctuation. The document title (`#`) may
  use title case. A heading may be a noun phrase; body copy may not be a fragment.
  A heading is also a link target — when you change one, update the in-repo links to
  it in the same commit.
- **D3.** Address the reader as *you*. Refer to Zentaizo in the third person by name.
  Name the actor rather than writing *we*.
- **D4.** Give at least one worked example for each user-facing capability: the exact
  command and what it writes or prints. End-user examples do not require Pixi —
  `pixi run …` belongs only in contributor instructions.
- **D5.** Keep the reference/design division. `README.md`, `docs/cli.md`,
  `docs/workspace-format.md`, and `docs/use-cases.md` say what a user does and what
  Zentaizo does; rationale, alternatives, and rejected options belong in
  `docs/design/`. README-level explanations stay short and example-driven.
- **D6.** A **subsystem** design doc under `docs/design/` opens with the line
  `_Distilled design doc — current architecture + rationale._` and uses the sections
  *What it is*, *Architecture*, *Key decisions*, *Considered and not taken*, and
  *See also*. A dated `## Decision update — YYYY-MM-DD` section may be appended when a
  decision changes. The rule does not reach the two files in that directory that are
  not subsystem docs: `README.md` is an index, and `versioning.md` states a policy.
- **D7.** A passage that tells an agent to read fetched material states that the
  material is untrusted input, or links to the section that does.

## Diction

- **X1.** Define each domain term at its first appearance on a page, then use it
  unchanged. The definitions are in § Canonical terms.
- **X2.** Use exactly one term per concept. Never vary a term for style — a reader
  takes the variation for a distinction being drawn.
- **X3.** Spell out an abbreviation at first use. Write *that is* and *for example*,
  not *i.e.* and *e.g.*
- **X4.** Write complete, punctuated sentences. No exclamation points and no
  superlatives. A bolded lead-in phrase may open a paragraph or a list item as a
  signpost — "**Neither term is canonical.**" — but everything after it is a sentence.
- **X5.** Quote code as code, copied verbatim from the source: file paths, CLI
  subcommands, flags, JSON keys, and field values go in backticks. A literal name is
  never a vocabulary violation, even where it differs from the canonical prose term.
  `sessions/changes/` is a path and `zentaizo next-change` is a subcommand; the concept
  either one holds is a **slice**.
- **X6.** Prefer the everyday word unless the technical word is more precise. Give
  every quantity a unit. Use American spelling.

## Claims

- **C1.** Replace a performance adjective with a measured value and the conditions it
  holds under. `docs/workspace-format.md` gives a cold graph build as "about a minute
  of local compute" alongside the extraction mode it measures; "fast" would say
  nothing.
- **C2.** Name the baseline, the workload, and the environment for every comparison. A
  comparative with no named baseline — "more token-efficient", "faster than scanning
  the repo" — is a defect, not a summary.
- **C3.** State a capability's limits in the same passage as the capability. `README.md`
  describes `zentaizo sandbox` as a guardrail against accidental writes and says in the
  same paragraph that a shell command can still slip past file-tool denies.
- **C4.** Describe mechanism, not effect. Name what Zentaizo reads, computes, writes,
  and prints: "the summarize prompt asks the agent to rewrite only the sources
  whose locked identity changed", not "summaries stay relevant".
- **C5.** Hedge what is not demonstrated. Do not hedge what you measured or read out of
  the code.
- **C6.** Cite the implementation for every claim about generated output, schema, or
  CLI surface — the function or constant in `src/zentaizo/`, or the command whose
  output you ran and pasted. `docs/design/session-model.md` does this when it follows
  the registry's field list with "Schema in `new_efforts_registry()` /
  `_main_effort()` (`src/zentaizo/cli.py`)". Copy a documented flag or default from the
  argument parser, never from memory: an uncited behavioral claim cannot be audited, and
  is the class of statement most likely to go stale.
- **C7.** Document released behavior in user-facing docs. Unimplemented design belongs
  under `docs/design/`, labeled as proposed or not implemented in the same sentence —
  as `docs/design/integrations.md` labels the Context Hub tier. A user-facing doc may
  point at a design doc for planned work; it must not describe planned work as
  something the reader can run.

## Canonical terms

Each concept below carries one canonical term, used in every governed file. The **Not**
column lists the wordings that lose, so that drift is greppable.

### Workspace objects

| Concept | Use | Not |
|---|---|---|
| The directory `zentaizo create` makes | **workspace** (a *zen workspace* where the sentence also discusses another kind) | context workspace, atlas directory, context directory, project |
| `zentaizo.atlas.json`, the human-authored statement of intent | **atlas** (*context atlas* at first mention on a page) | manifest, config, configuration file, source list |
| `zentaizo.lock.json`, the machine-resolved state | **lock** (or the filename) | lockfile, lock file, state file |
| One atlas entry: a repo, doc, paper, or note | **source** | input, asset |
| The `edit`/`reference` field on a repo entry | **role**; in prose, an **editable repo** and a **reference repo** | read-write repo, writable repo, read-only repo, upstream repo |
| A generated markdown condensation under `summaries/` | **summary** | digest, abstract, synopsis |
| The Graphify-built store under `graphify-out/` | **graph** (*knowledge graph* at first mention on a page) | index, code graph, graph database, KG |

*read-only* and *writable* stay reserved for describing sandbox permissions, where they
name an access mode rather than a category of repo.

### Session artifacts

| Concept | Use | Not |
|---|---|---|
| A named body of work that may span several editable repos | **effort** | workstream, initiative, epic, project, campaign, milestone |
| The numbered unit of work an effort decomposes into | **slice** | as a name for that unit: change, task, increment, chunk, phase, ticket, sub-effort |
| The document describing an effort or a slice | **plan** (*plan doc* where the file, not the content, is meant) | planning doc, spec, writeup, design doc (reserved for `docs/design/`) |
| The paste-ready execution prompt for the implementing agent | **handoff** | hand-off, briefing, kickoff prompt, instructions doc |
| A living, evidence-backed synthesis under `reports/` | **report** | synthesis (as the artifact's name), brief, study, analysis doc |
| Pre-decision input under `brainstorming/` | **brainstorming note** | brainstorm (as a noun), ideas doc, scratch note |
| The editor ledger in session-file frontmatter | **`edited_by`** | updated field, last-modified field, author list |

**`slice` versus `plan`.** A slice is the *unit of work*; a plan is the *document* that
describes one. An effort has a plan, and a slice has a plan; only the slice is a slice.
Both words are load-bearing in the code — `slice` names the entity throughout
`src/zentaizo/cli.py`, including the `zentaizo path slice <id>` subcommand — so do not
collapse them.

Session-file frontmatter carries no `updated:` field. The most recent `edited_by:`
entry *is* the last-modified record; `created:` is the stable creation timestamp.

### Actors, tools, and states

| Concept | Use | Not |
|---|---|---|
| The AI system reading the workspace and doing the work | **agent** | assistant, bot, *AI* as a noun for the actor, *the model* where the actor is meant |
| The host program the agent runs in (Claude Code, Codex CLI, Gemini CLI, Aider) | **harness** | host tool, client, IDE (unless an IDE is literally meant) |
| A specific model identity, as recorded in attribution | **model** (as in `edited_by`, and in *model-agnostic*) | model-neutral, AI-agnostic, vendor-neutral |
| This project | **Zentaizo** for the project, **the Zentaizo CLI** (or `zentaizo`) where the command-line program specifically is meant | *the tool*, zen (the `zen-` prefix names a workspace, not the project) |
| A derived artifact behind the inputs it was built from | **stale** (summaries, the graph) | out of date, rotted, expired |
| A record that has diverged from what it describes | **drift** (a rendered sandbox config against the atlas; docs against code) | skew, desync |
| The integer in the lock's `conventions` block | **conventions generation** | convention version, format version, schema version, workspace version |

**Why *agent* and not *assistant*.** The two appear about equally often in this
repository, so usage alone does not settle it. The field's own adjective decides it:
this is agentic software development, not assistant software development, and the
entry-point file every workspace ships is `AGENTS.md`. *agentic* and *agentically*
therefore share a root with the noun, and a harness's own feature names stay as that
harness spells them — a Claude Code *subagent*, for instance.

The generated workspace text still says *assistant* in 22 places against 10 for *agent*.
That is a divergence to close, not a precedent to follow. The glossary reaches generated
output as well as prose, and correcting it is a conventions change (see § What this
guide governs), so it is sequenced separately from the documentation pass.

**Some of these greps need judgment rather than replacement.** Read each hit:

- *change* remains the ordinary English word for an edit to code, and is banned only as
  the name of the unit of work. The same holds for *phase*, *task*, and *increment*:
  a workflow has phases and a release increments a version number.
- *plan* is correct wherever the document is what is meant.
- *the tool* always loses, but which term replaces it is a context call: **Zentaizo**
  for the project and its workspace format, **the Zentaizo CLI** for the command-line
  program. Where the sentence means a harness, it means neither.

**Neither *spoke* nor *hub* is canonical vocabulary.** They describe one particular
dogfooding arrangement — this repository's canonical checkout living inside a
`zen-zentaizo` workspace — and not the workspace model Zentaizo implements. Explain
that arrangement in `AGENTS.md` if it needs explaining; keep it out of the product
vocabulary.

## Sources

The rules restate established guidance rather than inventing house preferences:

- George Gopen and Judith Swan, "The Science of Scientific Writing", *American
  Scientist* 78:550–558 (1990) — reader expectations, the stress position, and
  subject-verb proximity (S1, S2, P1, P2, P3).
- Joseph Williams, *Style: Lessons in Clarity and Grace* — nominalizations, actors as
  subjects, and cutting empty modifiers (S2, S3, S6).
- The Nature and PLOS author guides — present-tense description of behavior, defined
  terms, and units (S4, X1, X6).
- The JOSS review criteria — a worked example and a stated scope for research software
  (D1, D4).
- The ACM SIGPLAN empirical-evaluation guidelines — measured values with their
  conditions, named baselines, and stated limits (C1, C2, C3).
- The Google and Microsoft documentation style guides — second person, sentence-case
  headings, one term per concept, and spelled-out abbreviations (D2, D3, X2, X3, X4).

This file extends two pieces of in-repo guidance rather than replacing them.
`AGENTS.md` § Style asks for short, example-driven README prose, detailed design
material in `docs/`, the atlas read as intent and the lock as resolved state, and no
Pixi in end-user examples. `docs/design/README.md` says what a distilled design doc is.

Pinning a project's documentation style in a repo-level guide is common practice; the
immediate prompt for this one was the `docs/STYLE.md` in Claude Observatory
(`cell-observatory/claude-observatory`, Apache-2.0). The rules above are re-derived
from the sources listed here, and the glossary is Zentaizo's own.
