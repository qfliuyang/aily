# Docker Full Flow Findings

## 2026-05-04 Initial Failure Summary

- The previous DIKIWI-only Docker run was not valid full-flow proof because it skipped Reactor and Entrepreneur.
- The 10-PDF Docker full-flow run failed before business execution.
- The failure was not a mock: manifest claims `mocked=false`, `real_files=true`, `real_graph_db=true`, `real_vault=true`, `real_llm=true`.

## Concrete Failure Modes From 10-PDF Run

- Docker extraction parity problem: every sampled PDF logged `Docling extraction failed ... No module named 'docling'`.
- Runtime problem: `dikiwi_batch` exceeded 3600 seconds before 07/08 could run.
- Batch stage problem: at least one DATA pipeline timed out after 300 seconds during the run.
- Graph quality problem: graph edge distribution is dominated by tags and generic relations.
- Upper DIKIWI contamination: generated Wisdom/Insight text included graph-artifact diagnostics such as self-referential edges, tag collapse, page-level containers, and false topology.
- Business proof gap: 07-Proposal and 08-Entrepreneurship remained empty.

## Quantitative Evidence

- Stage counts: 00-Chaos 11, 01-Data 189, 02-Information 169, 03-Knowledge 61, 04-Insight 23, 05-Wisdom 21, 06-Impact 6, 07-Proposal 0, 08-Entrepreneurship 0.
- Graph counts: information 169, tag 363, edges 763.
- Relation distribution: has_tag 572, enables 58, depends_on 46, part_of 42, tradeoff_with 17, applies_to 11, example_of 7, supports 4, contradicts 4, validates 1, extends 1.
- Recent graph nodes include generic labels like Page 1 through Page 10.
- LLM trace: 86 records, 83 successes, 3 incomplete/cancelled records.

## Immediate Hypotheses

- Page labels are entering graph as real information nodes and causing cross-document collisions.
- Tag nodes dominate topology and should not be treated as semantic evidence for higher-stage synthesis.
- Generic relation types are not enough to represent meaningful EDA/innovation connections.
- Per-source upper-stage fanout is too slow for 10 PDFs; batch-level subgraph synthesis is needed.
- Docker dependency list is not aligned with the extraction code path.

## Code Findings

- `NetworkSynthesisSelector.assess()` is tag-anchored: it iterates all current node tags, expands `has_tag` neighborhoods, and includes a synthetic tag node in each candidate.
- Candidate scoring counts all edges, so `has_tag` edges inflate density and score.
- `candidate_nodes_to_information()` converts every information node from selected tag neighborhoods, including generic labels like `Page 1`.
- `ImpactAgent._graph_centers()` uses top edge-count information nodes without filtering page/container labels or tag-dominated hubs.
- Batch upper DIKIWI executes Insight/Wisdom/Impact per successful Knowledge context, which creates expensive fanout for 10 PDFs.

## Fixes Started

- `NetworkSynthesisSelector` now considers only semantic tags as retrieval anchors.
- Candidate nodes now exclude synthetic tag nodes and generic page/slide/container labels.
- Candidate edges now exclude `has_tag`, self-loops, and non-information endpoints before scoring/prompting.
- `candidate_nodes_to_information()` now skips generic information nodes.
- `InformationAgent` now persists only semantic graph tags as tag bridge nodes.
- `ImpactAgent` now uses semantic information-to-information center nodes and filters generic page centers.
- `GraphDB` has `get_top_information_nodes_by_semantic_edge_count()`.
- `scripts/audit_dikiwi_quality.py` now supports full-flow strict checks: business-required, tag-edge ratio, generic page nodes, unresolved wikilinks.
- `scripts/run_docker_full_flow_pressure.py` creates a repeatable Docker full-flow pressure run.

## Strict Audit Result On Old Failed Evidence

- Strict audit fails the old 10-PDF run with:
  - LLM trace contains failed/cancelled records.
  - `07-Proposal` missing.
  - `08-Entrepreneurship` missing.
  - `tag_edge_ratio=0.7497`.
  - 90 generic page information nodes.
  - 85 unresolved wikilinks.

## 2026-05-04 Docker Build Finding

- A 2-PDF Docker probe did not reach application startup because image build failed during export.
- Root cause: mandatory `docling>=2.0.0` pulled the full Docling standard stack, including Torch and NVIDIA CUDA libraries such as `libcusparse.so.12`.
- Impact: Docker Desktop filled the host volume and then stopped accepting Docker API connections.
- Fix applied: Docling is no longer a mandatory dependency in `requirements.txt`; the Docling runtime path is optional and falls back to MinerU/pdfplumber extraction when unavailable.
- Harness fix applied: Docker evidence writer caps large logs and no longer masks primary failures with secondary disk-write failures.
- Remaining blocker: Docker daemon must be restarted/recovered before 2-PDF, 5-PDF, and 10-PDF Docker validation can continue.
