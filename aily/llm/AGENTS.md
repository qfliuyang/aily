<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# llm

## Purpose

LLM abstraction layer. Provides a unified `LLMClient` interface, active runtime routing for Kimi and DeepSeek, legacy coding-plan adapters, workload-aware dispatch, rate limiting via `LLMRouter`, and a centralized prompt registry. Thinking mode is disabled by default for batch speed. Timeout: 300s.

## Key Files

| File | Description |
|------|-------------|
| `client.py` | `LLMClient` — unified async interface, retry logic, usage tracking |
| `llm_router.py` | `LLMRouter` — rate limiting, provider-specific builders, `for_task()` auto-select |
| `provider_routes.py` | `PrimaryLLMRoute` — workload-aware routing, `resolve_route()`, 4 providers |
| `prompt_registry.py` | `DikiwiPromptRegistry` — centralized prompt templates |
| `kimi_client.py` | `KimiClient` — Kimi/Moonshot-specific helpers (chat_json, classify, synthesize) |
| `coding_plan_client.py` | Coding plan LLM client with multi-provider support (Ark, Bailian, Zhipu) |
| `conversation_logger.py` | LLM call logging for debugging |

## For AI Agents

### Working In This Directory
- New providers: add a `route_*` method to `PrimaryLLMRoute`, add to `LLMRouter`, add a `ProviderRoute`
- Prompts: add to `DikiwiPromptRegistry` as static methods
- Rate limits: `max_concurrency` and `min_interval_seconds` in SETTINGS
- `thinking=False` is the default — only enable for complex reasoning stages
- Workload routing: configure `llm_workload_routes_json` for per-stage provider overrides
- Never call provider APIs directly from outside this package

### Testing Requirements
- `tests/llm/` covers client behavior
- Mock `LLMClient` for unit tests that don't need real LLM calls

### Common Patterns
- `await client.chat(messages=[...], temperature=0.3)` — standard chat
- `await client.chat_json(messages=[...])` — JSON-structured output
- Usage stats: `client.get_usage_stats()` returns calls, tokens

## Dependencies

### Internal
- `aily/config.py` — SETTINGS for API keys and model selection

### External
- `httpx` / `aiohttp` — HTTP transport
- `openai` — OpenAI-compatible client

<!-- MANUAL: -->
