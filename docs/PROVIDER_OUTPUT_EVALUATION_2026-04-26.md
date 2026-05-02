# Provider Output Evaluation: Zhipu vs Kimi vs DeepSeek

Date: 2026-04-26

## Scope

This report compares three real Aily output vaults generated from the same pipeline shape:

- `test-vault-zhipu`
- `test-vault-kimi`
- `test-vault-deepseek`

This is an output-quality evaluation, not a raw API benchmark. The goal is to judge which provider currently produces better DIKIWI, Reactor, and Entrepreneur results inside Aily.

## Method

The comparison used direct inspection of the vault contents:

- stage counts from `00-Chaos` through `08-Entrepreneurship`
- note graph connectivity based on Obsidian `[[wikilinks]]`
- proposal uniqueness and specificity
- entrepreneur completeness and failure noise
- obvious extraction residue such as `tabletr`, `rowspan`, and `colspan`
- sample note review from `07-Proposal` and `08-Entrepreneurship`

## Executive Summary

### Overall ranking

1. **DeepSeek**: strongest upper-layer synthesis, best proposal specificity, best entrepreneur completeness
2. **Kimi**: most stable fallback, but more repetitive and more generic at the proposal layer
3. **Zhipu**: currently weakest because rate limiting visibly corrupts entrepreneur output

### Main conclusion

Provider choice matters most from `03-Knowledge` upward.

- `01-Data` and `02-Information` differences are mostly count and phrasing differences.
- `03-08` differences are structural and material.
- DeepSeek currently gives the best `Insight -> Wisdom -> Proposal -> Entrepreneur` chain.
- Zhipu is not acceptable for `08-Entrepreneurship` in the current runtime because too many outputs contain obvious failed panel actions.

### Cross-provider problems

All three providers still share these pipeline weaknesses:

- `00-Chaos` notes are graph-isolated
- `07-Proposal` notes have no `[[wikilinks]]`
- `08-Entrepreneurship` notes have no `[[wikilinks]]`
- HTML/table residue still leaks into some notes
- `06-Impact` flatlines at `9` notes in all three runs, which looks like a pipeline constraint rather than real model convergence

## Stage Count Comparison

| Stage | Zhipu | Kimi | DeepSeek |
|------|------:|-----:|---------:|
| `00-Chaos` | 11 | 11 | 11 |
| `01-Data` | 168 | 218 | 227 |
| `02-Information` | 74 | 140 | 178 |
| `03-Knowledge` | 95 | 90 | 127 |
| `04-Insight` | 15 | 14 | 34 |
| `05-Wisdom` | 12 | 13 | 41 |
| `06-Impact` | 9 | 9 | 9 |
| `07-Proposal` | 5 | 6 | 9 |
| `08-Entrepreneurship` | 9 | 11 | 11 |

### Interpretation

- **Zhipu** is sparse in `02-05`, suggesting weaker graph expansion and weaker higher-order synthesis.
- **Kimi** is stronger than Zhipu in `01-02`, but does not convert that advantage into stronger `04-05`.
- **DeepSeek** clearly expands the network best at `03-05`, especially in `Insight` and `Wisdom`.

## Graph Structure Comparison

| Metric | Zhipu | Kimi | DeepSeek |
|-------|------:|-----:|---------:|
| Total notes | 398 | 512 | 647 |
| Connected components | 54 | 111 | 104 |
| Largest component | 56 | 106 | 100 |

### Stage-level graph behavior

- `00-Chaos` is fully isolated in all three vaults.
- `01-Data` has no outbound links in all three vaults, but it is linked *to* by `02-Information`.
- `07-Proposal` is fully isolated in all three vaults.
- `08-Entrepreneurship` is fully isolated in all three vaults.

### Implication

The DIKIWI middle stack is working better than before, but the business layers are still detached from the graph. This is a pipeline design problem, not a provider problem.

## Proposal Layer Comparison

## Zhipu

Zhipu produced `5` proposal notes. The sample proposal at [test-vault-zhipu/07-Proposal/2026-04-26_0606_Residual_Analysis_Report_Electro_Temporal_Co_Optimization_and_IR_Driven_Placement_in_Advanced_Node_EDA.md](/Users/luzi/code/aily/test-vault-zhipu/07-Proposal/2026-04-26_0606_Residual_Analysis_Report_Electro_Temporal_Co_Optimization_and_IR_Driven_Placement_in_Advanced_Node_EDA.md:8) is coherent and domain-relevant. Its proposal wedge is concrete:

- pre-route IR hotspot prediction
- area-neutral decap filler cell optimization

However, the overall Zhipu proposal set is small, and it did not produce as much graph-driven upper-layer expansion before proposal generation.

## Kimi

Kimi produced `6` proposal notes, but only `4` unique proposal titles. One report title appears `3` times:

- `Residual_Analysis_EDA_Workflow_Intelligence_Signoff_Methodology_Lifecycle_and_Organizational_Memory_DIKIWI_Vault_Synthesis_Report`

The sample proposal at [test-vault-kimi/07-Proposal/2026-04-26_0648_Residual_Analysis_EDA_Workflow_Intelligence_Signoff_Methodology_Lifecycle_and_Organizational_Memory_DIKIWI_Vault_Synthesis_Report.md](/Users/luzi/code/aily/test-vault-kimi/07-Proposal/2026-04-26_0648_Residual_Analysis_EDA_Workflow_Intelligence_Signoff_Methodology_Lifecycle_and_Organizational_Memory_DIKIWI_Vault_Synthesis_Report.md:8) is thoughtful and technically literate, but it tends to drift toward:

- workflow intelligence
- methodology lifecycle management
- organizational memory

That framing is often valid, but it is less venture-sharp than the best DeepSeek output.

## DeepSeek

DeepSeek produced `9` proposal notes, all with unique titles. The sample at [test-vault-deepseek/07-Proposal/2026-04-26_0526_DIKIWI_Vault_Analysis_EDA_IR_Drop_Optimization_and_Knowledge_Management_Proposals.md](/Users/luzi/code/aily/test-vault-deepseek/07-Proposal/2026-04-26_0526_DIKIWI_Vault_Analysis_EDA_IR_Drop_Optimization_and_Knowledge_Management_Proposals.md:8) is the strongest proposal artifact among the three providers.

Strengths:

- grounded in a specific tradeoff: IR drop reduction vs timing closure
- ties proposals back to explicit wisdom nodes
- generates narrower product wedges
- avoids repeating the same organizational-memory framing

DeepSeek also generated the broadest proposal inventory while keeping titles unique.

## Entrepreneurship Layer Comparison

## Zhipu

Zhipu entrepreneur output is materially degraded by rate limiting. The note [test-vault-zhipu/08-Entrepreneurship/2026-04-26/denied-Adaptive_EM_Signoff_Engine_with_AI-Driven_Dynamic_Bypass.md](/Users/luzi/code/aily/test-vault-zhipu/08-Entrepreneurship/2026-04-26/denied-Adaptive_EM_Signoff_Engine_with_AI-Driven_Dynamic_Bypass.md:71) contains empty panel sections and repeated failed actions caused by `429 Too Many Requests`.

Measured failure markers in `08-Entrepreneurship`:

- `429` occurrences: `65`
- average failed actions per denied note: `10.2`
- notes with error actions: `10/10`

Conclusion: Zhipu cannot be trusted for entrepreneur evaluation in the current runtime configuration.

## Kimi

Kimi entrepreneur output is much more reliable than Zhipu, but still noisier than DeepSeek.

Measured failure markers:

- `429` occurrences: `0`
- `Empty response from LLM`: `2`
- average failed actions per denied note: `2.6`
- notes with error actions: `10/10`

The sample note [test-vault-kimi/08-Entrepreneurship/2026-04-26/denied-EM_Signoff_Methodology_Versioning_and_Exclusion_List_Intelligence.md](/Users/luzi/code/aily/test-vault-kimi/08-Entrepreneurship/2026-04-26/denied-EM_Signoff_Methodology_Versioning_and_Exclusion_List_Intelligence.md:7) is detailed and commercially literate, but Kimi still shows partial failure noise and produces very long entrepreneur notes.

## DeepSeek

DeepSeek has the cleanest entrepreneur layer. The sample note [test-vault-deepseek/08-Entrepreneurship/2026-04-26/denied-Cross-Project_IR_Learning_for_Early_Hotspot_Prediction.md](/Users/luzi/code/aily/test-vault-deepseek/08-Entrepreneurship/2026-04-26/denied-Cross-Project_IR_Learning_for_Early_Hotspot_Prediction.md:27) contains:

- a clean synthesis section
- coherent role-specific findings
- concrete blockers
- explicit market and workflow context

Measured failure markers:

- `429` occurrences: `0`
- `Empty response from LLM`: `0`
- average failed actions per denied note: `0.6`
- notes with error actions: `6/10`

DeepSeek still has some failure markers, but far fewer than the other two providers. It is currently the strongest entrepreneur evaluator.

## Note Length and Verbosity

| Stage | Zhipu avg words | Kimi avg words | DeepSeek avg words |
|------|-----------------:|---------------:|-------------------:|
| `01-Data` | 143.3 | 160.2 | 150.3 |
| `02-Information` | 184.4 | 196.9 | 190.0 |
| `03-Knowledge` | 119.0 | 162.4 | 85.5 |
| `04-Insight` | 252.7 | 295.9 | 344.7 |
| `05-Wisdom` | 367.8 | 534.5 | 470.3 |
| `06-Impact` | 224.2 | 320.2 | 265.7 |
| `07-Proposal` | 651.6 | 969.5 | 789.1 |
| `08-Entrepreneurship` | 2440.3 | 6188.1 | 4800.6 |

### Interpretation

- **Kimi** is the most verbose overall, especially in `07` and `08`.
- **DeepSeek** is less verbose than Kimi in `07-08`, but gives better density of useful content.
- **Zhipu** is shortest overall, but that is not a strength here because its entrepreneur output is shortened by failure, not by discipline.

## Extraction Residue

All three vaults contain the same count of obvious extraction residue markers:

- `tabletr` / `rowspan` / `colspan` / HTML table fragments: `8` notes each

Conclusion: upstream chaos/data normalization is currently a shared pipeline problem. Switching providers does not solve it.

## Provider-by-Provider Assessment

## Zhipu

### Strengths

- Can produce technically plausible DIKIWI and proposal text
- Proposal framing can be concrete when the run succeeds

### Weaknesses

- Entrepreneur layer is operationally compromised by rate limiting
- Upper-layer graph expansion is weak
- Lower proposal count than DeepSeek

### Best use

- Not recommended for `08-Entrepreneurship` until rate limiting and retry control are fixed
- Could still be tested for lower-cost `01-02` tasks if tightly paced

## Kimi

### Strengths

- Stable and generally coherent
- Stronger than Zhipu in `01-02`
- Produces detailed and commercially aware entrepreneur analysis

### Weaknesses

- Proposal layer is repetitive
- Tends to drift toward generic workflow/memory/platform narratives
- Verbosity is high relative to idea density

### Best use

- Good fallback for `01-Data` and `02-Information`
- Acceptable for business review if DeepSeek is unavailable

## DeepSeek

### Strengths

- Strongest `03-05` synthesis
- Best proposal specificity and diversity
- Best entrepreneur completeness
- Lowest operational failure noise in `08`

### Weaknesses

- Still shares graph-detachment problems with the other providers
- Still inherits extraction residue from upstream

### Best use

- Primary provider for `03-Knowledge` through `08-Entrepreneurship`

## Recommended Routing for Aily

### Recommended current routing

- `01-Data`: **Kimi**
- `02-Information`: **Kimi**
- `03-Knowledge`: **DeepSeek**
- `04-Insight`: **DeepSeek**
- `05-Wisdom`: **DeepSeek**
- `06-Impact`: **DeepSeek**
- `07-Proposal`: **DeepSeek**
- `08-Entrepreneurship`: **DeepSeek**

### Avoid for now

- `08-Entrepreneurship` on **Zhipu**

## Required Pipeline Fixes Before the Next Evaluation

1. Link `07-Proposal` notes back to their supporting `06/05/04` evidence chain.
2. Link `08-Entrepreneurship` notes back to the exact proposal and evidence notes they judged.
3. Fix the HTML/table residue that leaks from chaos extraction into downstream notes.
4. Investigate why `06-Impact` always stops at `9` notes regardless of provider.
5. Add provider-specific pacing and retry controls, especially for Zhipu.

## Final Judgment

If Aily must choose one provider today for the upper reasoning layers, the answer is **DeepSeek**.

If Aily wants a safer two-provider split, the most defensible current architecture is:

- **Kimi** for lower-layer structured extraction
- **DeepSeek** for graph reasoning, proposal generation, and entrepreneur evaluation

Zhipu is not disqualified forever, but its current entrepreneur results are too visibly degraded to treat as production-grade.
