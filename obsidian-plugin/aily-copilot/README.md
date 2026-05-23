# Aily Copilot Obsidian Plugin

Origin: Created by Codex lead agent on 2026-05-23.

This is the first Aily-Copilot companion plugin MVP. It is intentionally thin:
the plugin owns the Obsidian UI, while Aily's FastAPI backend owns vault search,
grounded chat, citations, dossier generation, DIKIWI, and future project logic.

## Install For Local Use

Copy this folder into:

```text
<vault>/.obsidian/plugins/aily-copilot/
```

Then enable **Aily Copilot** in Obsidian community plugin settings.

For the default local vault:

```text
/Users/luzi/Library/Mobile Documents/com~apple~CloudDocs/Documents/aily/.obsidian/plugins/aily-copilot/
```

## Backend

Start Aily:

```bash
uv run python -m aily.main
```

The plugin defaults to:

```text
http://127.0.0.1:8000
```

## Current Features

- Right-sidebar Aily chat view.
- Active-note-aware prompt seeding.
- Calls `/api/copilot/chat`.
- Shows citation-bearing Markdown answers.
- Calls `/api/copilot/dossiers/generate`.
- Optional LLM toggle for deterministic extractive mode.

## Next Features

- Context pills for selected text, folder, tags, and source sets.
- Citation cards with click-to-open excerpts.
- Project mode.
- Graph neighborhood panel.
- Preview-first write/edit workflow.
