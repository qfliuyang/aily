# Docker Full Flow Test And Improvement Plan

Goal: make Aily's Docker full-flow path execute real 00-Chaos through 08-Entrepreneurship for 10 PDFs without mocks, while exposing and fixing graph-quality and runtime failures.

## Current Failure Evidence

- Run: `logs/runs/2026-05-03T09-48-37Z_docker_real_llm_full_flow_10pdf`
- Manifest: `docker-volumes/data/logs/runs/2026-05-03T09-48-44Z_full_pipeline_10pdf/manifest.json`
- Failure: `Phase 'dikiwi_batch' exceeded 3600.0s`
- Partial output: 189 Data, 169 Information, 61 Knowledge, 23 Insight, 21 Wisdom, 6 Impact, 0 Proposal, 0 Entrepreneurship
- Graph: 169 information nodes, 363 tag nodes, 763 edges
- LLM trace: 86 records, 83 successes, 3 cancelled/incomplete records

## Phases

1. Diagnosis and plan
   - Status: complete
   - Extract concrete failure modes from 10-PDF Docker evidence.
   - Identify code locations responsible for Docker extraction parity, batch timeout behavior, graph artifact leakage, and full-flow evidence.

2. Docker extraction parity
   - Status: blocked
   - Fix missing `docling` or make the Docker extraction stack explicit and tested.
   - Ensure MinerU/PDF fallback can write cache without corrupting the input corpus.

3. Full-flow evidence harness
   - Status: complete
   - Add a dedicated Docker full-flow runner or extend the current runner so 10-PDF full-flow is one reproducible command.
   - Preserve partial evidence on timeout and classify timeout/cancelled LLM calls as failures.

4. DIKIWI graph quality filters
   - Status: complete
   - Prevent page/container nodes and generic structural tags from dominating upper DIKIWI synthesis.
   - Detect self-loops, tag-collapse, page-label collisions, and generic relation pollution before Insight/Wisdom/Impact.

5. Runtime scaling controls
   - Status: complete
   - Reduce unnecessary LLM calls and avoid per-source upper-stage fanout when batch graph synthesis can operate on selected subgraphs.
   - Make timeouts stage-specific and produce actionable telemetry.

6. Business layer full-flow
   - Status: in_progress
   - Run Reactor and Entrepreneur only after DIKIWI quality passes.
   - Verify 07-Proposal and 08-Entrepreneurship counts and content are connected to evidence chains.

7. Verification ladder
   - Status: pending
   - Fast unit/regression tests.
   - 2-PDF Docker full-flow.
   - 5-PDF Docker full-flow.
   - 10-PDF Docker full-flow.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| `python` not found for planning helper | Ran session catchup with `python` | Reran with `python3` |
| 10-PDF Docker full flow timed out | Real full-flow run with `--max 10 --force-business` | Added stricter audit and started graph-quality fixes; full rerun still pending |
| Graph synthesis treated tags/pages as signal | Inspected `NetworkSynthesisSelector`, graph relation counts, and generated Wisdom text | Patched tag/page/`has_tag` filters and semantic impact centers |
| Docker build pulled CUDA/Torch through mandatory `docling` | `scripts/run_docker_full_flow_pressure.py --max 2 --build` | Removed Docling from mandatory requirements, made Docling optional at runtime, capped wrapper evidence logs |
| Docker Desktop daemon unavailable after failed build | `docker info` / `docker system df` | Host recovered to ~7 GiB free, but Docker daemon still not accepting connections; Docker rerun is blocked until daemon starts |
