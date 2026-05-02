<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-26 | Updated: 2026-04-26 -->

# voice

## Purpose

Voice message handling. Downloads audio from Feishu, transcribes with OpenAI Whisper, and feeds transcripts into the DIKIWI pipeline.

## Key Files

| File | Description |
|------|-------------|
| `downloader.py` | Downloads voice files from Feishu message attachments |
| `transcriber.py` | `WhisperTranscriber` — OpenAI Whisper API client |

## For AI Agents

### Working In This Directory
- Voice messages are enqueued as jobs in `QueueDB`
- Transcription runs asynchronously
- Result text is passed to `DikiwiMind.process_input()`
- Supports multiple audio formats (m4a, mp3, wav)

### Common Patterns
- Job type: `voice_transcribe`
- `TranscriptionResult` contains text, language, duration
- Requires `WHISPER_API_KEY` or `OPENAI_API_KEY`

## Dependencies

### Internal
- `aily/queue/` — Job queue for async transcription
- `aily/bot/` — Feishu message handling

### External
- `httpx` — HTTP client for Whisper API
- OpenAI API key

<!-- MANUAL: -->
