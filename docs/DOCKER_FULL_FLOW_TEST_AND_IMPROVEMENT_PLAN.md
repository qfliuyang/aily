# Docker Full Flow Test And Improvement Plan

Date: 2026-05-04

## Goal

Make Docker full-flow acceptance prove the real Aily product path:

`10 PDFs -> 00-Chaos -> 01-Data -> 02-Information -> 03-Knowledge -> 04-Insight -> 05-Wisdom -> 06-Impact -> 07-Proposal -> 08-Entrepreneurship`

This gate must use real Docker containers, real mounted source files, real vault writes, real graph DB writes, real LLM calls, real Reactor proposals, and real Entrepreneur/Guru outputs. A DIKIWI-only run is not full-flow proof.

## Baseline Failure

Latest failed full-flow evidence:

- `logs/runs/2026-05-03T09-48-37Z_docker_real_llm_full_flow_10pdf`
- Manifest: `docker-volumes/data/logs/runs/2026-05-03T09-48-44Z_full_pipeline_10pdf/manifest.json`
- Failure: `Phase 'dikiwi_batch' exceeded 3600.0s`

Partial output:

- `00-Chaos`: 11 notes
- `01-Data`: 189 notes
- `02-Information`: 169 notes
- `03-Knowledge`: 61 notes
- `04-Insight`: 23 notes
- `05-Wisdom`: 21 notes
- `06-Impact`: 6 notes
- `07-Proposal`: 0 notes
- `08-Entrepreneurship`: 0 notes

Strict audit failures on that evidence:

- LLM trace contains cancelled/incomplete records.
- `07-Proposal` has no markdown notes.
- `08-Entrepreneurship` has no markdown notes.
- Graph is tag-edge dominated: `tag_edge_ratio=0.7497`.
- Graph contains 90 generic page information nodes.
- Vault contains 85 unresolved wikilinks.

## Test Contract

A Docker full-flow acceptance run is valid only if all of these are true:

- The run exits `0`.
- `manifest.json` reports `mocked=false`.
- `real_files`, `real_graph_db`, `real_vault`, and `real_llm` are all true.
- `00-Chaos` through `08-Entrepreneurship` all contain generated markdown.
- LLM trace has no failed, cancelled, or incomplete records.
- Graph is not dominated by `has_tag` edges.
- Graph contains no generic `Page N` / `Slide N` information nodes.
- Upper DIKIWI notes are about domain/innovation substance, not graph construction artifacts.
- Wikilinks resolve or are explicitly marked as external concepts.
- 07/08 outputs link back to Impact/Proposal evidence.

## Improvement Phases

1. Docker extraction parity
   - Keep the preprod image small enough to build and run.
   - Prove whether Docker uses MinerU, Docling, or pdfplumber for each PDF.
   - Fail the evidence gate if all rich extractors are unavailable and fallback quality is low.

2. Strict full-flow harness
   - Use `scripts/run_docker_full_flow_pressure.py --max 10 --build`.
   - Preserve Docker logs, source manifest, vault files, graph DB, LLM trace, stdout/stderr, and strict audit output.
   - Do not accept DIKIWI-only runs as full-flow proof.

3. Graph quality filters
   - Use tags only as retrieval anchors, not as evidence nodes.
   - Exclude `has_tag`, self-loops, and non-information endpoints from synthesis context.
   - Exclude generic page/slide/container nodes from higher DIKIWI.
   - Select Impact centers using semantic information-to-information edges.

4. Runtime scaling
   - Bound expensive upper DIKIWI work to the highest-scored graph-change contexts.
   - Track stage-level elapsed time, LLM calls, token use, and cancelled tasks.
   - Keep stage timeouts meaningful; do not simply raise timeouts to hide scaling failures.

5. Business-layer acceptance
   - Run Reactor only after DIKIWI strict audit passes.
   - Run Entrepreneur/Guru against every proposal.
   - Require non-empty `07-Proposal` and `08-Entrepreneurship`.
   - Reconcile proposal counts against entrepreneurship decisions.

## Commands

Full-flow pressure run:

```bash
uv run python scripts/run_docker_full_flow_pressure.py --max 10 --build
```

Strict audit against an existing run:

```bash
uv run python scripts/audit_dikiwi_quality.py \
  --vault logs/runs/<run_id>/docker-volumes/vault \
  --graph-db logs/runs/<run_id>/docker-volumes/vault/.aily/graph.db \
  --llm-log logs/runs/<run_id>/docker-volumes/data/e2e/<llm_calls>.jsonl \
  --output logs/runs/<run_id>/full-flow-quality-report.json \
  --require-business \
  --strict-graph \
  --max-unresolved-wikilinks 0
```

## Fixes Started

- Added semantic graph filters for NetworkSynthesisSelector.
- Filtered generic page/slide/container information nodes out of upper DIKIWI.
- Excluded tag nodes and `has_tag` edges from synthesis candidates.
- Added semantic information-center query for Impact.
- Made InformationAgent persist only semantic graph tags.
- Added strict audit options for business output, graph pollution, and unresolved links.
- Added repeatable Docker full-flow pressure runner.
- Added extraction-method evidence to full-pipeline reports.
- Added graph-change-score selection for bounded higher-order DIKIWI contexts.
- Added Docker env controls for higher-order context count, Reactor method timeout, Entrepreneur timeout, and proposal count.
- Added real LLM-backed Reactor fallback proposal generation when all configured methods return no usable proposals.
- Removed mandatory `docling` from runtime requirements after Docker proved it pulls a Torch/CUDA-scale stack; Docling is now optional and MinerU/pdfplumber remain the preprod path.
- Capped Docker wrapper evidence logs so disk-full secondary failures do not mask the primary failure.

## Open Risks

- A 10-PDF rerun after the first fixes is still required.
- A 2-PDF Docker probe is currently blocked because Docker Desktop stopped accepting API connections after the failed CUDA/Torch build filled local storage.
- MinerU availability in Docker is still not proven by this first patch.
- Business layers may expose separate timeout or quality failures after DIKIWI reaches 06 cleanly.
