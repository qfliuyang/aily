from __future__ import annotations

from pathlib import Path

from aily.security.backup import create_backup, restore_backup
from aily.security.rate_limit import FixedWindowRateLimiter


def test_fixed_window_rate_limiter_rejects_abuse() -> None:
    limiter = FixedWindowRateLimiter(max_requests=2, window_seconds=60)

    assert limiter.allow("client-1")[0] is True
    assert limiter.allow("client-1")[0] is True
    allowed, retry_after = limiter.allow("client-1")

    assert allowed is False
    assert retry_after > 0


def test_backup_restore_reconstructs_vault_graph_and_sources(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    source_objects = tmp_path / "sources"
    graph_db = tmp_path / "graph.db"
    source_db = tmp_path / "source_store.db"
    backup_path = tmp_path / "backup.zip"
    restore_dir = tmp_path / "restore"

    (vault / "00-Chaos").mkdir(parents=True)
    (vault / "00-Chaos" / "note.md").write_text("# Note", encoding="utf-8")
    source_objects.mkdir()
    (source_objects / "object").write_bytes(b"raw")
    graph_db.write_bytes(b"graph")
    source_db.write_bytes(b"source-db")

    manifest = create_backup(
        vault_path=vault,
        graph_db_path=graph_db,
        source_store_db_path=source_db,
        source_object_dir=source_objects,
        output_path=backup_path,
    )
    restored = restore_backup(backup_path=backup_path, restore_dir=restore_dir)

    assert manifest.vault_files == 1
    assert manifest.source_files == 1
    assert (restore_dir / "vault" / "00-Chaos" / "note.md").read_text(encoding="utf-8") == "# Note"
    assert (restore_dir / "graph" / "graph.db").read_bytes() == b"graph"
    assert restored["manifest"]["vault_files"] == 1
