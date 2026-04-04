# Critic Report — Aily Autopilot Phase 1 Spec

Date: 2026-04-05  
Scope: Week 1 reactive pipeline plus accepted CEO/Eng review expansions  
Verdict: **REJECT** — Multiple feasibility risks, scope contradictions, and missing prerequisites make this spec non-actionable as written.

---

## 1. Logical Gaps / Unstated Assumptions

### 1.1 No Obsidian Local REST API contract defined
The spec says the writer will "post via Local REST API" but never names the endpoint, request body, or plugin. Obsidian's Local REST API is a third-party plugin (not core). The spec assumes the plugin is installed and configured, but does not specify:
- Which plugin (e.g., `coddingtonbear/obsidian-local-rest-api`)
- Which endpoint (`/vault/` vs `/active/`)
- How to create folders via REST (some endpoints do not auto-create directories)
- Encoding behavior for Chinese filenames

**Recommendation:** Add a prerequisites section: "Obsidian Local REST API plugin vX.Y installed, HTTPS certificate accepted, API key stored in `.env`.

### 1.2 URL extraction is undefined
The webhook receiver must "extract URL from text message body," but Feishu messages can contain multiple URLs, markdown, or URLs inside brackets. There is zero specification for:
- Regex or library to use
- Which URL wins if multiple exist
- Whether to reject messages with zero URLs or treat them as a different job type

**Recommendation:** Define URL extraction using a tested regex (e.g., `urllib.parse` + `re.findall`) and specify behavior for 0, 1, and N URLs.

### 1.3 Dedup TTL is the wrong layer
The spec deduplicates webhook `event_id` with a 60s TTL, but Feishu webhooks already have a challenge/verification handshake and event IDs. If Feishu retries after 60s, Aily will reprocess. More importantly, there is no mention of deduplicating the *same URL sent twice* by the user intentionally or via passive capture.

**Recommendation:** Keep `event_id` dedup for idempotency, but add `url_hash` dedup against the raw ingestion log (already noted in TODOS but not integrated into the spec).

### 1.4 Missing failure signal for Feishu push
The queue worker "dequeues → fetches → parses → writes → Feishu confirmation reply." If parsing fails or the page is paywalled, the Feishu push module must send a failure message, but the spec does not define the payload shape or how the worker communicates the failure reason to the push module.

**Recommendation:** Add an error taxonomy (e.g., `FETCH_FAILED`, `PARSE_FAILED`, `OBSIDIAN_REJECTED`) and pass it through the job result object.

---

## 2. Overcomplexity / Simpler Approaches

### 2.1 BrowserUseManager subprocess is premature optimization for Week 1
The spec demands a dedicated subprocess with IPC queue for Browser Use, but Week 1's success criteria only require serializing concurrent URL submissions. An `asyncio.Semaphore(1)` around a single Playwright context in the main process achieves the same serialization with 90% less code. The subprocess adds IPC complexity, multiprocessing Queue serialization limits, and process-leak handling before the core pipeline is proven.

**Recommendation:** Defer the subprocess manager to Week 2. Use a single Playwright context with `asyncio.Semaphore(1)` in Week 1. If OOM becomes real, then add the subprocess.

### 2.2 APScheduler for a daily digest placeholder is dead code
The scheduler section includes APScheduler and a daily digest cron, but the digest is not in Week 1 success criteria and has no implementation detail. It is a liability: more dependencies, more threads, more failure modes.

**Recommendation:** Remove APScheduler from Week 1. Add it when the digest feature is actually designed.

### 2.3 json-repair is a band-aid, not a strategy
The LLM client spec says "`json-repair` for malformed JSON." Relying on `json-repair` means you are already accepting unreliable LLM outputs. A simpler and more robust approach is to request structured JSON mode (Anthropic) or use Pydantic validation with graceful fallbacks.

**Recommendation:** Remove `json-repair` from the stack. Use Pydantic model validation and a typed degrade response instead.

---

## 3. Feasibility Risks

### 3.1 Browser Use dependency is unproven on Chinese SPAs
TODOS.md explicitly flags this: "Before trusting Browser Use for Monica/Kimi URLs, verify it correctly extracts Chinese text from JS-rendered pages." The spec treats Browser Use as a solved dependency despite this being a known uncertainty. If Browser Use fails, the entire Week 1 pipeline collapses.

**Risk level: HIGH.**  
**Recommendation:** Block Week 1 implementation on a Day 1 spike that validates Browser Use against a local Chinese SPA fixture and a public Chinese web page. Do not write the manager until the spike passes.

### 3.2 Feishu voice message webhook capability is unverified
TODOS.md notes: "Confirm that Feishu bot webhooks deliver voice messages as audio file URLs." The spec's Vision mentions "voice memos" as an input source, but Week 1 does not scope voice memo implementation. This creates scope ambiguity.

**Recommendation:** Explicitly exclude voice memos from Week 1 until the Feishu payload is validated.

### 3.3 "Browser must use isolated profile" is hand-wavy
The constraints say "Browser must use isolated profile (no interference with active sessions)," but the spec does not explain how Playwright/Browser Use will achieve this. Playwright's persistent context can collide with the user's main Chrome profile if paths overlap. Browser Use may require its own profile directory configuration.

**Recommendation:** Specify the profile directory path (e.g., `~/.aily/browser_profile`) and document how it is cleaned on startup/shutdown.

### 3.4 No local development fixture for end-to-end test
`test_e2e.py` is supposed to run a mocked Feishu outbound + Obsidian API end-to-end, but there is no mention of a local HTTP fixture server for the URL fetch step. Without a fetchable local page, the e2e test is incomplete.

**Recommendation:** Add a `pytest` fixture that spins up a local `http.server` with a static HTML page so the full pipeline can be exercised.

---

## 4. Missing Dependencies / Sequencing Issues

### 4.1 No Python project skeleton exists
The file structure shows `aily/main.py`, `requirements.txt`, `pytest.ini`, etc., but none of these files exist in the repository. The spec jumps straight to feature implementation without a project bootstrap step.

**Recommendation:** Add a Day 0 task to create `pyproject.toml` (or `setup.py`), `.gitignore`, `requirements.txt`, and a pytest configuration with `pytest-asyncio`.

### 4.2 `browser-use` package compatibility is unspecified
`browser-use` is a rapidly evolving package. The spec does not pin a version or document installation steps (it requires Playwright browser downloads).

**Recommendation:** Pin `browser-use==0.x.x` in `requirements.txt` and add a setup instruction: `playwright install chromium`.

### 4.3 Feishu bot registration must happen before any webhook code
The spec lists the webhook receiver as Component 1, but 小刘 cannot test it without a Feishu app ID, verification token, and encrypt key. These approvals take time.

**Recommendation:** Add a prerequisites section with a Day 0 checklist: Feishu app registered, webhook URL exposed (ngrok or Tailscale), verification token obtained.

### 4.4 Obsidian vault path and plugin configuration are prerequisites
`OBSIDIAN_VAULT_PATH` and `OBSIDIAN_REST_API_KEY` are in `.env`, but the writer cannot function without the Local REST API plugin installed and the vault being accessible.

**Recommendation:** Add a Day 0 checklist for Obsidian plugin installation and REST API key generation.

### 4.5 LLM client is not used in Week 1
The spec includes an `LLMClient` component, but none of the Week 1 features (reactive URL pipeline) require LLM calls. Parsers are described as "regex patterns to parser functions." Including the LLM client now is speculative hardware.

**Recommendation:** Remove `LLMClient` from Week 1. Add it when the parsing or tagging pipeline actually needs it.

---

## 5. Security Concerns

### 5.1 `.env` file is the only credential storage mentioned
The constraints say "All secrets in `.env` only, never committed," but `.env` files are plaintext on disk and are frequently leaked in backups, screenshots, or accidental commits. macOS has Keychain; the spec ignores it.

**Recommendation:** At minimum, support reading secrets from environment variables (already implied by `python-dotenv`) so 小刘 can inject them via shell profile or 1Password CLI. Document that `.env` is a convenience, not a security boundary.

### 5.2 Feishu webhook has no signature verification
The spec says "Parse `event_id`, dedup with 60s TTL" but does not mention verifying the Feishu webhook signature using `FEISHU_ENCRYPT_KEY`. Without signature verification, anyone who discovers the webhook URL can spam the queue.

**Risk level: MEDIUM.**  
**Recommendation:** Add signature verification to the webhook receiver using the Feishu challenge/encrypt key handshake before any enqueueing.

### 5.3 Browser profile directory will contain session cookies
An isolated browser profile can still persist session cookies for Monica, Kimi, and other services. If the macOS account is shared or backed up, those cookies are exposed.

**Recommendation:** Document that the profile directory should be inside `~/.aily` (not the system temp dir) and excluded from Time Machine backups. Consider encrypting sensitive cookies in the future.

### 5.4 LLM API keys are sent without specifying transport security
The spec does not mention using `https` for LLM calls or validating certificates. While Anthropic/OpenAI clients do this by default, it should be explicit.

**Recommendation:** Add a constraint: "All external HTTP calls use TLS 1.2+ with certificate validation enabled."

---

## 6. Testability Concerns

### 6.1 `test_fetcher.py` depends on Browser Use, which requires a real browser
Testing Browser Use "on local HTML fixture" is harder than it sounds. Browser Use is designed for live web pages; running it against `file://` fixtures may fail due to CORS, missing JS execution context, or Browser Use's own URL validation.

**Recommendation:** Run a spike test before writing `test_fetcher.py`. If Browser Use cannot load `file://` or `http://localhost` fixtures, switch the test to a mocked Browser Use response and validate the integration layer instead.

### 6.2 `test_e2e.py` has no assertions defined
The spec names the test file but does not say what it should assert beyond "mocked Feishu outbound + Obsidian API end-to-end." What is the pass/fail criteria?

**Recommendation:** Define e2e test assertions explicitly:
1. Webhook POST returns 200.
2. Queue job transitions to `completed`.
3. Obsidian API receives a POST with expected frontmatter.
4. Feishu push API receives a success message.

### 6.3 No test for concurrent serialization
Success criterion says "Concurrent URL submissions → serialized, no OOM." There is no test file for this behavior.

**Recommendation:** Add a stress test (or at least a concurrency unit test) that submits N URLs simultaneously and verifies only one browser context is active at a time.

### 6.4 Parser registry has no test contract
`test_parser_registry.py` is mentioned in TODOS but not in the Week 1 test list. The spec lists 5 tests, but the accepted CEO-review expansion adds 6 more. The plan is inconsistent about which tests belong to Week 1 vs. later.

**Recommendation:** Explicitly scope tests to Week 1. If parser registry is Week 1, add it to the main test list and define the success/failure paths (e.g., unrecognized URL → generic fallback parser).

### 6.5 Missing contract for mocked Obsidian API
`test_writer.py` says "Obsidian API mocked responses (200, 404, connection refused)," but the spec does not define the expected request shape. A test cannot be written without knowing the endpoint, headers, and body format.

**Recommendation:** Define the Obsidian writer API contract in the spec before tests are written.

---

## Top 5 Critical Improvements (In Order)

1. **Validate Browser Use on Chinese content before writing any manager code.**  
   Add a Day 0 spike task. If it fails, pivot to `playwright` direct extraction or a simpler fetcher.

2. **Remove subprocess/IPC complexity from Week 1.**  
   Replace `BrowserUseManager subprocess` with an in-process Playwright context + `asyncio.Semaphore(1)`. Defer the subprocess to Week 2 or later.

3. **Define the Obsidian Local REST API contract explicitly.**  
   Specify the endpoint, plugin name, request body, and folder creation behavior. Without this, the writer and its tests are unimplementable.

4. **Add Feishu webhook signature verification.**  
   Without it, the queue is open to spam. Use the Feishu encrypt key to verify payloads before enqueueing.

5. **Strip dead components from Week 1 (LLM client, APScheduler digest, voice memos).**  
   They add dependencies and failure modes to a pipeline that does not use them. Re-introduce each only when its feature is actually in scope.

---

## Bottom Line

The spec describes a plausible system, but it tries to build too many moving parts in Week 1. The highest-leverage move is to shrink the Week 1 surface to: FastAPI webhook + SQLite queue + in-process Playwright fetch + simple parser + Obsidian writer + Feishu reply. Everything else (subprocess, APScheduler, LLM client, voice memos) should be deferred until the reactive pipeline is proven end-to-end.
