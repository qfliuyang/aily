# Aily TODOS

## Deferred from Eng Review

### Evaluate SQLite connection pooling for GraphDB and QueueDB
- **What:** Both GraphDB and QueueDB open/close connections per call. Under concurrent load this may become a bottleneck.
- **Why:** The eng review flagged per-call connection open/close as a potential performance issue once ingestion and graph pipelines run concurrently.
- **Context:** Evaluate aiosqlite connection pool options or switch to a shared async connection with WAL mode. Only optimize if profiling shows it matters.
- **Priority:** P2

### Validate Browser Use with Chinese-language and dynamic-content pages
- **What:** Before trusting Browser Use for Monica/Kimi URLs, verify it correctly extracts Chinese text from JS-rendered pages.
- **Why:** 小刘's core workflow involves Chinese-language AI tools. If Browser Use fails on these, the prototype is dead on arrival.
- **Context:** Should be done during Day 4 of the prototype build (fetcher implementation). Create a small script that points Browser Use at a local Chinese SPA fixture and a real Monica/Kimi URL to confirm text extraction quality.
- **Depends on:** Browser Use dependency installed, Playwright browsers downloaded.

## Bridge to MVP (from Design Doc)

- Week 2: Add Kimi report parsing and cross-model verification.
- Weeks 3–4: Build the planner → agent pipeline and the SQLite entity graph.
- Weeks 5–6: Add daily digest scheduling and Zettelkasten link suggestions.
- Weeks 7–8: Integrate Monica chat extraction and Claude Code session capture.
- Weeks 9–10: Installer DMG, keychain-based credential storage, and Tailscale-accessible remote controls.

## Deferred from CEO Review (2026-04-05)

### Define entity graph schema (BUILD NOW)
- **What:** Define the SQLite table schema for the entity graph (nodes, edges, occurrences) and the query interface used by collision detection and voice-memo auto-tagging.
- **Why:** Weekly insight collision reports and voice-memo auto-tagging were accepted into scope, but the design doc only says "lightweight SQLite graph" with no concrete definitions.
- **Context:** Need tables for `nodes` (type, label, source, created_at), `edges` (relation_type, weight, source), and `occurrences` (linking entities to raw log entries). The collision detector queries for co-occurring entities across different source conversations. Define this during Weeks 3–4.
- **Effort:** M → S
- **Priority:** P1
- **Depends on:** SQLite queue schema defined.

### Verify Feishu voice message webhook payload (BUILD NOW)
- **What:** Confirm that Feishu bot webhooks deliver voice messages as audio file URLs, and document the payload format and download auth.
- **Why:** Voice memo quick-capture was accepted into scope but depends on an unverified Feishu API capability.
- **Context:** During Day 1–2 Feishu validation, send a voice message to the test bot and inspect the webhook payload. If Feishu does not support voice messages via webhook, pivot voice memos to text-only or use a different entry point.
- **Effort:** S → S
- **Priority:** P1
- **Depends on:** Feishu test app registered.

### Build BrowserUseManager with subprocess queue (BUILD NOW)
- **What:** Create a single `BrowserUseManager` that runs Browser Use in a dedicated subprocess/queue. Both the queue worker and passive capture cron enqueue fetch tasks to this subprocess rather than launching Playwright directly.
- **Why:** The original design only protected the queue worker with `asyncio.Semaphore(1)`. Passive capture runs on an APScheduler cron outside the worker. A subprocess queue provides true isolation, prevents concurrent Playwright instances from OOMing 小刘's Mac, and simplifies process lifecycle management.
- **Context:** Implement during Day 3–4. The subprocess handles Playwright context lifecycle (start/stop) and returns page text or errors to the main process via a simple IPC queue.
- **Effort:** S-M → S
- **Priority:** P1
- **Depends on:** Browser Use dependency installed.

### Expand test plan for accepted scope expansions (DONE)
- **What:** Add test files for passive capture, voice memos, auto-parser registry, learning loop, weekly collision reports, and LLM client failure modes.
- **Why:** The original 5-test plan covers the reactive URL pipeline but has zero coverage for the 5 CEO-review expansions.
- **Context:** Test plan artifact written to `~/.gstack/projects/aily/luzi-unknown-eng-review-test-plan-20260405-074351.md`. Required test files: `tests/test_passive_capture.py`, `tests/test_voice.py`, `tests/test_parser_registry.py`, `tests/test_learning_loop.py`, `tests/test_collisions.py`, `tests/test_llm_client.py`. Cover happy path + at least one failure path per file.
- **Effort:** M → S
- **Priority:** P1
- **Depends on:** Core test suite skeleton exists.

### Implement Obsidian draft folder + aily_generated frontmatter (DONE)
- **What:** Aily writes all new notes to a staging / draft folder inside the vault with `aily_generated: true` and `aily_written_at` timestamps. The learning loop only triggers on notes that have been moved out of the draft folder and subsequently edited.
- **Why:** The pure frontmatter + 5-second cooldown approach is not reliable enough. A draft folder eliminates false positives entirely by making user "approval" (moving the note) the signal that the note is part of the permanent vault.
- **Context:** Implement in the writer module. The file watcher monitors the main vault (not the draft folder) for edits to notes that originated from Aily.
- **Effort:** S → S
- **Priority:** P1
- **Depends on:** Writer module design complete.
- **Completed:** v0.1.0.0 (2026-04-05)

### Add URL dedup hash in raw ingestion log
- **What:** Hash incoming URLs with SHA256 and deduplicate against the raw ingestion log before enqueueing.
- **Why:** Passive capture may discover URLs that 小刘 also shares manually. Without dedup, the pipeline processes the same content twice.
- **Context:** Add a `url_hash` column to the SQLite queue or raw log. Check it before creating a new job.
- **Effort:** S → S
- **Priority:** P2
- **Depends on:** SQLite queue schema defined.

### Add LLM timeout/retry/degrade spec
- **What:** Document and implement explicit timeout, retry, and graceful-degradation behavior for every LLM-dependent path (tagging, collision detection, preference inference, planning).
- **Why:** The current design doc lacks any LLM failure handling. LLM calls can timeout, return empty responses, or return malformed JSON.
- **Context:** Specify: timeout threshold (e.g., 60s), retry count (1), fallback behavior (simpler prompt, skip feature, or queue for later). Use `json-repair` or similar for malformed JSON recovery.
- **Effort:** S → S
- **Priority:** P2
- **Depends on:** Planner agent design complete.

### Define Monica/Kimi DOM selectors or run discovery spike
- **What:** Identify the exact DOM selectors or detection strategy for finding new Monica chats and Kimi reports during passive capture.
- **Why:** Passive capture requires browser automation against authenticated pages. The selectors are currently unknown.
- **Context:** Run a discovery spike with Browser Use against 小刘's actual Monica and Kimi accounts (in the isolated profile). Document the selectors. If selectors are unstable, consider a URL-list-based detection strategy instead.
- **Effort:** M → S
- **Priority:** P1
- **Depends on:** Feishu/Mobile auth working in isolated browser profile.

### Add jitter/backoff to passive capture cron (BUILD NOW)
- **What:** Replace the hard 5-minute cron with an interval timer that adds 0-60s jitter per run and backs off (up to 30 min) after consecutive failures. Architected as "hybrid Phase 1" so if polling gets banned we can pivot to an intercept approach.
- **Why:** A hard 5-minute cron against authenticated services is likely to trigger rate limits or bot detection. The eng review selected a phased approach: smart polling first, with fallback to manual URL sharing and a future event-driven intercept if needed.
- **Context:** Implement in the scheduler module. Log each backoff event. If passive capture fails for >24h, alert 小刘 and fall back to manual sharing.
- **Effort:** S → S
- **Priority:** P1
- **Depends on:** BrowserUseManager implemented.

