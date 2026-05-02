from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aily.main import _configure_frontend_static


def test_frontend_static_serves_index_and_spa_fallback(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>Aily Studio</html>", encoding="utf-8")

    app = FastAPI()
    _configure_frontend_static(app, dist)

    client = TestClient(app)

    assert "Aily Studio" in client.get("/").text
    assert "Aily Studio" in client.get("/studio/graph").text
    assert client.get("/api/missing").status_code == 404
