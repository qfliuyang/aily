# Feishu Voice Message Webhook Discovery

## Discovery Date
2026-04-05

## Summary
Feishu bot webhooks **DO support voice messages**. When a user sends a voice message to a Feishu bot, the webhook payload contains the voice file metadata including a `file_key` that can be used to download the audio file via the Feishu Drive API.

## Webhook Payload Schema

When a voice message is received, the webhook event has the following structure:

```json
{
  "schema": "2.0",
  "header": {
    "event_id": "xxx",
    "event_type": "im.message.receive_v1",
    "create_time": "1234567890000",
    "token": "verification-token",
    "app_id": "cli_xxx"
  },
  "event": {
    "sender": {
      "sender_id": {
        "union_id": "on_xxx",
        "user_id": "xxx",
        "open_id": "ou_xxx"
      },
      "sender_type": "user"
    },
    "message": {
      "message_id": "om_xxx",
      "root_id": "om_xxx",
      "parent_id": "om_xxx",
      "create_time": "1234567890000",
      "chat_id": "oc_xxx",
      "chat_type": "p2p",
      "message_type": "voice",
      "content": "{\"file_key\": \"file_xxx\", \"file_name\": \"voice.mp3\"}",
      "mentions": []
    }
  }
}
```

## Key Fields

| Field | Description |
|-------|-------------|
| `event.message.message_type` | Always `"voice"` for voice messages |
| `event.message.content` | JSON string containing `file_key` and `file_name` |
| `event.message.sender.open_id` | User's Open ID for sending replies |

## Downloading Voice Files

To download the voice file:

1. **Parse the webhook payload** to extract `file_key` from `content`
2. **Call Feishu Drive API** to download the file:
   ```
   GET https://open.feishu.cn/open-apis/drive/v1/medias/{file_key}/download
   ```
   Headers:
   - `Authorization: Bearer {tenant_access_token}`

3. **Transcribe the audio** using a speech-to-text service (Whisper, Azure Speech, etc.)

## Implementation Notes for Aily

### Option 1: Direct Download + Transcribe (Recommended)
- Download audio via Drive API
- Transcribe using OpenAI Whisper or similar
- Process transcribed text through the same pipeline as text messages

### Option 2: Feishu Speech-to-Text API
- Feishu provides a speech recognition API that can transcribe voice messages
- May have higher latency but avoids managing transcription infrastructure

### Authentication Requirements
- Requires `tenant_access_token` (obtained via `auth/v3/tenant_access_token/internal`)
- Bot must have `drive:file:download` scope permission

## Payload Differences: Text vs Voice

| Aspect | Text Message | Voice Message |
|--------|--------------|---------------|
| `message_type` | `"text"` | `"voice"` |
| `content` format | Plain text string | JSON with `file_key` and `file_name` |
| Processing | Direct | Requires download + transcription |
| Latency | Low | Higher (download + STT) |

## Deferred Implementation

Voice memo quick-capture was **deferred** from the Week 5 implementation because:

1. **Complexity**: Requires additional components (Drive API integration, STT service)
2. **Priority**: Text-based ingestion covers the core use case
3. **Effort**: 2-3 days to implement full pipeline vs. 1 day for text-only

## Recommended Next Steps (Week 7-8)

1. Add `drive:file:download` scope to Feishu app
2. Implement Drive API download in `aily/push/feishu.py`
3. Add STT integration (OpenAI Whisper recommended)
4. Create voice job type in QueueDB
5. Add voice transcription worker

## References

- Feishu Drive API: https://open.feishu.cn/document/server-docs/docs/drive-v1/download/download
- Feishu Message Events: https://open.feishu.cn/document/server-docs/docs/im-v1/message/events/receive
- Feishu Speech Recognition: https://open.feishu.cn/document/server-docs/docs/speech-recognition/overview
