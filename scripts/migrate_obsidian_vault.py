#!/usr/bin/env python3
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path("/Users/luzi/obsidian/aily")
NESTED = ROOT / "aily"
STAMP = datetime.now().strftime("%Y-%m-%d")
ARCHIVE_ROOT = ROOT / "4-Archives" / f"vault-migration-{STAMP}"
BACKUP_ROOT = ARCHIVE_ROOT / "backup"
RETIRED_ROOT = ARCHIVE_ROOT / "retired-nested-vault"


def ensure_dirs() -> None:
    for path in [
        ROOT / "0-Inbox",
        ROOT / "1-Projects",
        ROOT / "2-Areas",
        ROOT / "3-Resources",
        ROOT / "3-Resources" / "Literature",
        ROOT / "3-Resources" / "Templates",
        ROOT / "3-Resources" / "MOCs",
        ROOT / "3-Resources" / "Zettelkasten",
        ROOT / "4-Archives",
        ARCHIVE_ROOT,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def copy_backup() -> None:
    if NESTED.exists() and not BACKUP_ROOT.exists():
        shutil.copytree(NESTED, BACKUP_ROOT, dirs_exist_ok=True)


def same_file(a: Path, b: Path) -> bool:
    return a.exists() and b.exists() and a.read_bytes() == b.read_bytes()


def safe_move(src: Path, dst: Path) -> Path | None:
    if not src.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        if src.is_file() and dst.is_file() and same_file(src, dst):
            src.unlink()
            return dst

        stem = dst.stem
        suffix = dst.suffix
        i = 1
        while True:
            candidate = dst.with_name(f"{stem}-imported-{i}{suffix}")
            if not candidate.exists():
                dst = candidate
                break
            i += 1

    shutil.move(str(src), str(dst))
    return dst


def merge_dir(src: Path, dst: Path, skip_names: set[str] | None = None) -> None:
    if not src.exists():
        return
    skip_names = skip_names or set()
    dst.mkdir(parents=True, exist_ok=True)

    for item in sorted(src.iterdir()):
        if item.name in skip_names:
            continue
        target = dst / item.name
        if item.is_dir():
            merge_dir(item, target)
            if item.exists():
                try:
                    item.rmdir()
                except OSError:
                    pass
        else:
            safe_move(item, target)


def promote_obsidian_config() -> None:
    src = NESTED / ".obsidian"
    dst = ROOT / ".obsidian"
    if src.exists() and not dst.exists():
        shutil.move(str(src), str(dst))


def migrate_root_notes() -> None:
    for name in ["Home.md", "README.md", "VAULT-IMPROVEMENTS.md", "2026-04-12.md", "Untitled.canvas"]:
        safe_move(NESTED / name, ROOT / name)


def migrate_para_folders() -> None:
    merge_dir(NESTED / "0-Inbox", ROOT / "0-Inbox")
    merge_dir(NESTED / "1-Projects", ROOT / "1-Projects")
    merge_dir(NESTED / "2-Areas", ROOT / "2-Areas")
    merge_dir(NESTED / "4-Archives", ROOT / "4-Archives")


def migrate_resources() -> None:
    resources = NESTED / "3-Resources"

    merge_dir(resources / "Literature", ROOT / "3-Resources" / "Literature")
    merge_dir(resources / "Templates", ROOT / "3-Resources" / "Templates")

    maps_root = ROOT / "3-Resources" / "MOCs"
    merge_dir(resources / "MOCs", maps_root)
    merge_dir(ROOT / "3-Resources" / "Zettelkasten" / "Maps of Content", maps_root)

    legacy_index = resources / "Zettelkasten" / "0 Index.md"
    if legacy_index.exists():
        safe_move(legacy_index, ARCHIVE_ROOT / "Legacy-Zettelkasten-Index.md")

    merge_dir(resources / "Zettelkasten", ROOT / "3-Resources" / "Zettelkasten")

    maps_dir = ROOT / "3-Resources" / "Zettelkasten" / "Maps of Content"
    if maps_dir.exists():
        for item in maps_dir.iterdir():
            safe_move(item, maps_root / item.name)
        try:
            maps_dir.rmdir()
        except OSError:
            pass


def retire_nested_vault() -> None:
    if not NESTED.exists():
        return
    RETIRED_ROOT.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(NESTED), str(RETIRED_ROOT))


def write_report() -> None:
    report = ARCHIVE_ROOT / "migration-report.md"
    report.write_text(
        "\n".join(
            [
                "# Obsidian Vault Migration",
                "",
                f"- Date: {STAMP}",
                f"- Canonical vault root: {ROOT}",
                f"- Nested vault backup: {BACKUP_ROOT}",
                f"- Retired nested vault: {RETIRED_ROOT}",
                "",
                "## Canonical structure",
                "- 0-Inbox",
                "- 1-Projects",
                "- 2-Areas",
                "- 3-Resources/Literature",
                "- 3-Resources/Templates",
                "- 3-Resources/MOCs",
                "- 3-Resources/Zettelkasten",
                "- 4-Archives",
                "- DIKIWI",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    if not NESTED.exists():
        raise SystemExit(f"Nested vault not found: {NESTED}")

    ensure_dirs()
    copy_backup()
    promote_obsidian_config()
    migrate_root_notes()
    migrate_para_folders()
    migrate_resources()
    write_report()
    retire_nested_vault()
    print(f"Migration complete. Canonical vault root: {ROOT}")
    print(f"Backup: {BACKUP_ROOT}")
    print(f"Retired nested vault: {RETIRED_ROOT}")


if __name__ == "__main__":
    main()
