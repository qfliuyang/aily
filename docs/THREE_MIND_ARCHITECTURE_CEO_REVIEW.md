# CEO Review: Aily Three-Mind DIKIWI Architecture Plan

**Review Date:** 2026-04-09
**Review Mode:** SELECTIVE EXPANSION (User selected Approach B: Full Three-Mind Architecture)
**Sections Completed:** 10/10
**Critical Gaps Found:** 7

---

## Completion Summary Table

| Section | Finding | Severity |
|---------|---------|----------|
| 1. Intent Validation | DIKIWI pipeline adds cognitive load without clear ROI measurement | MEDIUM |
| 2. User Value Chain | Innovation/Entrepreneur minds risk noise vs signal for single user | HIGH |
| 3. Build vs Buy | Existing gating system covers 70% of value — leverage it | MEDIUM |
| 4. Risk Surface | 19 new files, 4-week timeline, multiple failure modes | HIGH |
| 5. Business Model | No clear monetization path for "three minds" differentiation | MEDIUM |
| 6. Competitive Position | TRIZ/GStack niche vs general knowledge management | LOW |
| 7. Team Velocity | Async batch minds add maintenance burden | MEDIUM |
| 8. Exit Optionality | Path dependency on DIKIWI model limits pivot flexibility | MEDIUM |
| 9. Technical Debt | Innovation/Entrepreneur minds share 60% code but not abstracted | MEDIUM |
| 10. Long-Term Trajectory | New engineer onboarding cost (metaphor not self-evident) | MEDIUM |

---

## Verdict

**CONDITIONAL APPROVE** — Proceed with DIKIWI Mind only (continuous knowledge processing). Defer Innovation and Entrepreneur minds until DIKIWI proves value retention.

The user has explicitly chosen full architecture despite recommendations. Critical gaps must be addressed before Week 3 implementation.

---

## NOT in Scope (Must Be Explicit)

The following are NOT covered by this plan and will cause surprises if assumed:

### Operational Gaps
1. **No failure recovery specification** — If Innovation Mind crashes mid-session, state is lost. No resume mechanism.
2. **No rate limiting** — LLM calls for 3 parallel minds could hit API limits. No queue priority.
3. **No observability** — No metrics on "how many insights generated" or "user actually read proposals."
4. **No A/B testing** — No way to compare Innovation vs no-Innovation outcomes.

### Integration Gaps
5. **No Feishu thread management** — Daily proposals will spam chat. No threading/collapse mechanism.
6. **No Obsidian template customization** — Hardcoded proposal formats may not match user's vault structure.
7. **No mobile experience** — 8am/9am sessions assume user is at desktop.

### Business Gaps
8. **No value capture metrics** — "Proposals generated" ≠ "Proposals acted upon."
9. **No degradation path** — If LLM API fails, entire Three-Mind system stops. No local fallback.
10. **No data retention policy** — Proposals accumulate forever. No archival/deletion strategy.

---

## Error & Rescue Registry

### Anticipated Failures

| Error Scenario | Likelihood | Impact | Rescue Path |
|----------------|------------|--------|-------------|
| Innovation Mind generates 10 low-quality proposals daily | HIGH | User ignores all proposals | Confidence threshold tuning + user feedback loop |
| DIKIWI atomicization produces fragmented/incoherent notes | MEDIUM | Knowledge graph polluted | Human-in-the-loop review before GraphDB write |
| Scheduler drift (8am/9am sessions fire at wrong times) | MEDIUM | User misses live sessions | Idempotent session IDs + deduplication |
| LLM API timeout during Entrepreneur evaluation | MEDIUM | Business proposals incomplete | Retry with simpler prompt, queue for later |
| Proposal storage bloat (1000+ proposals unarchived) | MEDIUM | Obsidian vault cluttered | Auto-archive proposals older than 30 days |
| GraphDB connection pool exhaustion | LOW | All minds stop processing | Connection retry with exponential backoff |
| Feishu rate limiting on daily notifications | MEDIUM | Notifications dropped silently | Batch notifications, status dashboard |

### Safety Mechanisms Required

1. **Circuit breaker** — If 3 consecutive sessions fail, auto-disable that mind and alert user
2. **Proposal quality gate** — Minimum confidence 0.5 is too low. Require 0.7 for Feishu notification.
3. **Manual override** — User can disable any mind via Feishu command: "disable innovation mind"
4. **Session replay** — Complete session logs for debugging proposal generation decisions

---

## TODOS.md Updates Required

Add the following critical gaps to TODOS.md under a new section "Critical Gaps from Three-Mind CEO Review":

```markdown
## Critical Gaps from Three-Mind CEO Review (2026-04-09)

### CG-1: Add circuit breaker for mind failures
- **What:** Implement circuit breaker pattern that disables a mind after 3 consecutive failures
- **Why:** Prevents cascading failures and spam from broken sessions
- **Scope:** InnovationMind and EntrepreneurMind schedulers
- **Priority:** P0
- **Effort:** S

### CG-2: Implement proposal quality gate (0.7 confidence threshold)
- **What:** Raise minimum confidence for Feishu notifications from 0.5 to 0.7
- **Why:** 0.5 produces too much noise; user will ignore all proposals
- **Scope:** aily/proposals/formatter.py notification logic
- **Priority:** P0
- **Effort:** XS

### CG-3: Add session replay logging
- **What:** Complete session logs (input → processing → output) for debugging
- **Why:** When proposals are bad, need to trace why
- **Scope:** aily/sessions/session.py logging
- **Priority:** P1
- **Effort:** M

### CG-4: Build manual override commands
- **What:** Feishu commands to enable/disable each mind: "disable innovation mind"
- **Why:** User needs escape hatch when minds are noisy
- **Scope:** aily/bot/message_intent.py + ws_client.py
- **Priority:** P1
- **Effort:** S

### CG-5: Implement proposal auto-archive (30 days)
- **What:** Auto-move proposals older than 30 days to archive folder
- **Why:** Prevents Obsidian vault clutter
- **Scope:** aily/proposals/storage.py archival logic
- **Priority:** P2
- **Effort:** S

### CG-6: Add mind-specific observability metrics
- **What:** Track proposals generated, read rate, action rate per mind
- **Why:** Validate that minds are actually useful
- **Scope:** New metrics module or integration with existing analytics
- **Priority:** P1
- **Effort:** M

### CG-7: Design Feishu thread management for proposals
- **What:** Collapse daily proposals into threaded messages instead of spam
- **Why:** 10 proposals/day × 2 minds = 20 messages. Unacceptable noise.
- **Scope:** aily/push/feishu.py threading support
- **Priority:** P0
- **Effort:** M
```

---

## Review Readiness Dashboard

| Criterion | Status | Notes |
|-----------|--------|-------|
| Clear user value proposition | ⚠️ PARTIAL | Single user may not need 3 minds |
| Technical feasibility | ✅ YES | 70% code exists, well-understood |
| Resource constraints understood | ⚠️ PARTIAL | 4 weeks assumes no interruptions |
| Failure modes documented | ❌ NO | Needs Error & Rescue section |
| Observability plan defined | ❌ NO | No metrics specified |
| Degradation path clear | ❌ NO | All-or-nothing LLM dependency |
| Team capacity confirmed | ✅ YES | One engineer (小刘) + AI assistance |
| External dependencies mapped | ✅ YES | LLM API, Feishu, Obsidian |

---

## Recommendation

**Proceed with Week 1 (DIKIWI Mind) only.** Build observability and user feedback loops before adding Innovation and Entrepreneur minds.

The architecture is sound but the risk of noise overwhelming signal is high. Start with the continuously-running DIKIWI Mind, measure for 2 weeks, then decide if scheduled session minds add value.

If proceeding with full architecture despite this recommendation:
1. Implement CG-1 (circuit breaker) and CG-2 (quality gate) before Week 2
2. Implement CG-7 (thread management) before first Innovation session
3. Add user feedback capture (👍/👎 on proposals) by Week 3

---

*Review produced by plan-ceo-review skill. Mode: SELECTIVE EXPANSION. User override: Enabled full architecture despite recommendation for incremental approach.*
