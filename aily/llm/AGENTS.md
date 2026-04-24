<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# llm

## Purpose

LLM abstraction layer. Provides a unified `LLMClient` interface, provider-specific routing (Kimi, Zhipu), rate limiting via `LLMRouter`, and a centralized prompt registry. All LLM calls in the application go through this layer.

## Key Files

| File | Description |
|------|-------------|
| `client.py` | `LLMClient` — unified async interface, usage tracking |
| `llm_router.py` | `LLMRouter` — rate limiting, provider-specific builders |
| `provider_routes.py` | `PrimaryLLMRoute` — app-wide client builder from SETTINGS |
| `prompt_registry.py` | `DikiwiPromptRegistry` — centralized prompt templates |
| `kimi_client.py` | `KimiClient` — Kimi/Moonshot-specific helpers (chat_json, classify) |
| `coding_plan_client.py` | Coding plan LLM client with multi-provider support |
| `conversation_logger.py` | LLM call logging for debugging |

## For AI Agents

### Working In This Directory
- New providers: add a `route_*` method to `PrimaryLLMRoute` and `LLMRouter`
- Prompts: add to `DikiwiPromptRegistry` as static methods
- Rate limits: `max_concurrency` and `min_interval_seconds` in SETTINGS
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
- `openai` — OpenAI-compatible client (used for Kimi/Zhipu)

<!-- MANUAL: -->
