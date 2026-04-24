<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-19 | Updated: 2026-04-19 -->

# push

## Purpose

Outbound message delivery. Sends notifications, digests, and replies back to Feishu (Lark) chat.

## Key Files

| File | Description |
|------|-------------|
| `feishu.py` | `FeishuPusher` — sends messages and reactions via Feishu API |

## For AI Agents

### Working In This Directory
- `FeishuPusher` wraps the `lark_oapi` SDK
- Supports text, markdown, and interactive card messages
- Message reactions (emoji) for acknowledging receipt

### Common Patterns
- `send_message(receive_id, content)` — primary API
- Content is JSON-serialized Feishu message format
- Errors are logged but not retried (callers handle retry)

## Dependencies

### Internal
- `aily/digest/` — Digest pipeline pushes daily summaries
- `aily/sessions/` — Minds may push notifications

### External
- `lark_oapi` — Feishu/Lark SDK

<!-- MANUAL: -->
