# Aily-Copilot Development And Test Plan

Origin: Created by Codex lead agent on 2026-05-23.
Objective: Build an Aily-native Obsidian copilot that combines Obsidian
Copilot-style product interaction with Aily's DIKIWI, dossier, research, and
evidence capabilities.

## Product Definition

Aily-Copilot is the user-facing product layer for Aily's vault intelligence.
It should let a user chat with the iCloud Obsidian vault, retrieve grounded
context, reason through DIKIWI, generate dossiers and business materials, and
inspect the evidence chain behind every output.

The default working vault is:

```text
/Users/luzi/Library/Mobile Documents/com~apple~CloudDocs/Documents/aily
```

## Architecture

### Aily Backend

- Vault search and note reading.
- Citation-ready context envelopes.
- Graph neighborhood lookup.
- DIKIWI and business-planning workflow triggers.
- Dossier generation from Vault and Tavily evidence.
- Quality scoring for vault notes, graph structure, and generated materials.
- Event stream for tool calls and workflow progress.

### Obsidian Companion Plugin

- Chat panel.
- Context pills for `@note`, `@folder`, `@tag`, `@vault`, `@web`, `@dossier`.
- Inline citations and source previews.
- Relevant notes panel.
- Preview-first write/diff workflow.
- Project selector.
- Buttons for "Generate dossier", "Reason through DIKIWI", and "Trace claim".

The plugin should be thin. It should call Aily APIs and avoid duplicating
backend reasoning.

## Milestones

### AC0: Product Groundwork

Deliverables:

- Obsidian Copilot review captured in repo docs.
- Aily-Copilot plan captured in repo docs.
- iCloud vault configured as default development vault.

Tests:

- Compile check.
- Vault layout check.
- Secret scan for committed docs/scripts.

Gate:

- Plan and review are readable and actionable.
- No copied AGPL implementation code from Obsidian Copilot.

### AC1: Backend Vault Chat Foundation

Deliverables:

- `VaultSearchService` over the configured Obsidian vault.
- Search endpoint with deterministic lexical results and citation IDs.
- Read-note endpoint with chunking, wikilink extraction, and backlinks.
- Context-envelope endpoint with stable L1-L5-style layers and hashes.

Tests:

- Deterministic fixture-vault evidence script.
- Search returns expected title/path/tag/keyword matches.
- Read-note rejects path traversal.
- Context envelope hashes are stable for identical input.

Gate:

- A future plugin can ask Aily to search/read/build context without direct file
  system access.

### AC2: Grounded Vault Chat

Deliverables:

- Chat endpoint that answers using selected vault context.
- Provider routing through Kimi/DeepSeek.
- Inline citation catalog in responses.
- No-answer behavior when evidence is insufficient.

Tests:

- Fixture vault chat with known answer.
- Hallucination guard: unsupported question returns insufficient-evidence
  response.
- LLM traffic monitor confirms provider calls.

Gate:

- Answers cite vault notes and do not present unsupported claims as facts.

### AC3: Dossier From Chat

Deliverables:

- Generate dossier from a chat topic or selected notes.
- Dossier output under `10-Dossiers`.
- Claim-to-evidence table.
- Tavily augmentation when explicitly requested or configured.

Tests:

- Dossier generated from fixture vault and Tavily packet fixtures.
- Every claim has Vault or Tavily evidence.
- Unsupported hypotheses are labeled.
- Readability score meets threshold.

Gate:

- A human reviewer can read the dossier as a substantive learning artifact.

### AC4: Graph-Aware Knowledge Navigation

Deliverables:

- Graph neighborhood endpoint based on content links, backlinks, shared source
  IDs, tags, and DIKIWI lineage.
- Relevant notes endpoint.
- Relationship explanations: why note A connects to note B.

Tests:

- Fixture graph with expected edges.
- No artificial central hub links.
- Relationship explanations include evidence snippets.

Gate:

- Obsidian Graph View and Aily graph output both expose meaningful structure.

### AC5: Project Mode

Deliverables:

- Persistent Aily projects with includes/excludes, prompt, preferred models,
  source set, and workflow history.
- Project-scoped search and dossier generation.

Tests:

- Project A cannot retrieve excluded Project B notes.
- Folder/tag/source filters are enforced.
- Project state persists across process restart.

Gate:

- Users can run separate business or research workspaces without context bleed.

### AC6: Obsidian Companion Plugin MVP

Deliverables:

- Obsidian plugin scaffold.
- Connects to Aily backend with token auth.
- Chat panel, search/read, citations, and source preview.
- "Generate dossier" action.

Tests:

- Plugin build.
- Manual Obsidian smoke test against iCloud vault.
- API auth failure and success paths.

Gate:

- User can operate Aily from inside Obsidian for real work.

### AC7: Write Preview And Human Approval

Deliverables:

- Proposed-note write endpoint.
- Patch/diff preview model.
- Accept/reject audit trail.
- No direct edits to user-authored notes without approval.

Tests:

- Proposed edit does not alter target until approved.
- Accepted edit writes expected content.
- Rejected edit leaves target unchanged.

Gate:

- Aily can help improve notes without violating user trust.

## Quality Gates

Each gate needs multiple evidence sources:

- API response payloads.
- Runtime logs.
- Vault files.
- Source note excerpts.
- Citation catalog.
- Durable store records where applicable.
- Independent quality score.

Passing a gate requires content quality, not only file existence.

## First Implementation Slice

Build AC1 now:

1. Add `aily/copilot` package.
2. Add vault search/read/context services.
3. Add `/api/copilot` router.
4. Add deterministic backend evidence script.
5. Run compile and evidence script.

This creates the foundation for the Obsidian plugin and grounded vault chat.
