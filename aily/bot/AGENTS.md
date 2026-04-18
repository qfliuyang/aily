<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# bot

## Purpose

Feishu (Lark) bot integration layer. Handles inbound messages via WebSocket long connection and webhook, routes message intents, and pushes outbound replies back to Feishu chat.

## Key Files

| File | Description |
|------|-------------|
| `ws_client.py` | `FeishuWSClient` — WebSocket long connection to Feishu servers |
| `webhook.py` | FastAPI webhook endpoint for Feishu callbacks |
| `message_intent.py` | `IntentRouter` — classifies incoming messages by type |

## For AI Agents

### Working In This Directory
- WebSocket client is the primary inbound path (avoids public URLs)
- `IntentRouter` maps messages to `IntentType` enums
- All inbound messages are handed to `DikiwiMind.process_input()`

### Common Patterns
- `lark_oapi` SDK for Feishu API calls
- Messages are enqueued to `QueueDB` for async processing
- WebSocket reconnects with exponential backoff

## Dependencies

### Internal
- `aily/queue/` — SQLite job queue
- `aily/sessions/dikiwi_mind.py` — DIKIWI Mind message handler
- `aily/push/feishu.py` — Outbound message pushing

### External
- `lark_oapi` — Feishu/Lark official SDK

<!-- MANUAL: -->
