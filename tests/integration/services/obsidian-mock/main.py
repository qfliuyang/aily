"""
Obsidian Mock Service

Simulates Obsidian Local REST API for integration testing.
Stores notes in memory and provides inspection endpoints for tests.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Obsidian Mock Service")

# In-memory vault storage
vault: dict[str, str] = {}  # path -> content
API_KEY = "test-api-key"
VAULT_PATH = "/vault"


class NoteRequest(BaseModel):
    """Obsidian note creation request."""
    path: str
    content: str


class NoteResponse(BaseModel):
    """Obsidian note response."""
    path: str
    content: str
    created: bool
    modified: datetime


def verify_auth(authorization: Optional[str]) -> None:
    """Verify Bearer token matches expected API key."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    token = authorization.replace("Bearer ", "")
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "obsidian-mock", "notes_count": len(vault)}


@app.get("/")
async def root(authorization: Optional[str] = Header(None)) -> dict:
    """Root endpoint - returns vault info."""
    verify_auth(authorization)
    return {
        "status": "ok",
        "vault": "Test Vault",
        "version": "1.0.0-mock",
    }


@app.get("/vault/")
async def list_files(
    directory: Optional[str] = None,
    authorization: Optional[str] = Header(None),
) -> dict:
    """List files in vault."""
    verify_auth(authorization)

    files = []
    for path in vault.keys():
        if directory and not path.startswith(directory):
            continue
        files.append({
            "path": path,
            "name": Path(path).name,
        })

    return {"files": files}


@app.get("/vault/{filepath:path}")
async def get_note(
    filepath: str,
    authorization: Optional[str] = Header(None),
) -> dict:
    """Get note content."""
    verify_auth(authorization)

    if filepath not in vault:
        raise HTTPException(status_code=404, detail=f"Note not found: {filepath}")

    return {
        "path": filepath,
        "content": vault[filepath],
    }


@app.put("/vault/{filepath:path}")
async def create_or_update_note(
    filepath: str,
    request: Request,
    authorization: Optional[str] = Header(None),
) -> dict:
    """Create or update a note."""
    verify_auth(authorization)

    body = await request.body()
    content = body.decode("utf-8")

    created = filepath not in vault
    vault[filepath] = content

    logger.info(f"{'Created' if created else 'Updated'} note: {filepath}")

    return {
        "path": filepath,
        "content": content,
        "created": created,
        "modified": datetime.utcnow().isoformat(),
    }


@app.delete("/vault/{filepath:path}")
async def delete_note(
    filepath: str,
    authorization: Optional[str] = Header(None),
) -> dict:
    """Delete a note."""
    verify_auth(authorization)

    if filepath not in vault:
        raise HTTPException(status_code=404, detail=f"Note not found: {filepath}")

    del vault[filepath]
    logger.info(f"Deleted note: {filepath}")

    return {"status": "deleted", "path": filepath}


@app.post("/commands/")
async def execute_command(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> dict:
    """Execute an Obsidian command."""
    verify_auth(authorization)

    data = await request.json()
    command = data.get("command")

    logger.info(f"Executing command: {command}")

    # Mock response - in real Obsidian this would do something
    return {"status": "executed", "command": command}


@app.get("/active/")
async def get_active_file(
    authorization: Optional[str] = Header(None),
) -> dict:
    """Get currently active file."""
    verify_auth(authorization)

    # Return most recently modified file
    if not vault:
        return {"path": None}

    # For mock purposes, just return first file
    path = next(iter(vault.keys()))
    return {"path": path}


# Test inspection endpoints
@app.get("/__test/notes")
async def get_all_notes() -> dict:
    """Get all notes in vault (for test verification)."""
    return {
        "notes": [
            {"path": path, "content": content}
            for path, content in vault.items()
        ]
    }


@app.get("/__test/notes/search")
async def search_notes(q: str) -> dict:
    """Search notes by content."""
    results = []
    for path, content in vault.items():
        if q.lower() in content.lower() or q.lower() in path.lower():
            results.append({"path": path, "content": content})
    return {"results": results}


@app.post("/__test/reset")
async def reset_vault() -> dict:
    """Clear all notes (call between tests)."""
    vault.clear()
    logger.info("Vault reset")
    return {"status": "reset", "notes_count": 0}


@app.get("/__test/stats")
async def get_stats() -> dict:
    """Get vault statistics."""
    total_size = sum(len(c) for c in vault.values())
    return {
        "notes_count": len(vault),
        "total_size_bytes": total_size,
        "paths": list(vault.keys()),
    }
