#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.writer.dikiwi_obsidian import _slugify_title


ZK_ROOT = Path("/Users/luzi/obsidian/aily/3-Resources/Zettelkasten")


def extract_frontmatter_title(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    frontmatter = text[4:end]
    match = re.search(r'^title:\s+"?(.*?)"?$', frontmatter, re.MULTILINE)
    return match.group(1).strip() if match else None


def rename_note(path: Path) -> Path | None:
    title = extract_frontmatter_title(path)
    if not title:
        return None

    prefix = path.stem.split("-", 1)[0]
    new_name = f"{prefix}-{_slugify_title(title)}{path.suffix}"
    new_path = path.with_name(new_name)
    if new_path == path:
        return None

    counter = 1
    while new_path.exists():
        if new_path.read_text(encoding="utf-8") == path.read_text(encoding="utf-8"):
            path.unlink()
            return new_path
        new_path = path.with_name(f"{prefix}-{_slugify_title(title)}-{counter}{path.suffix}")
        counter += 1

    path.rename(new_path)
    return new_path


def main() -> None:
    renamed = 0
    for note in sorted(ZK_ROOT.rglob("*.md")):
        if note.name == "00 Zettelkasten Index.md":
            continue
        if rename_note(note):
            renamed += 1
    print(f"Renamed {renamed} Zettelkasten notes")


if __name__ == "__main__":
    main()
