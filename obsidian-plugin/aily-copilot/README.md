# Aily Copilot

Origin: Fork-derived local plugin based on `logancyang/obsidian-copilot`
commit `bd8829f`.

License: AGPL-3.0, inherited from Obsidian Copilot.

This plugin is the Obsidian-side product shell for Aily. It uses Obsidian's
native `requestUrl` API to call the local Aily FastAPI backend and provides:

- grounded vault chat
- citation display
- relevant note review
- dossier generation
- preview-first draft creation, apply, and reject

Default backend:

```text
http://127.0.0.1:8000
```

Build:

```bash
npm ci --ignore-scripts
npm run build
```

Install into the configured Aily vault from the repo root:

```bash
uv run python scripts/install_aily_copilot_plugin.py
```
