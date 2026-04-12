#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import re


AILY_VAULT = Path("/Users/luzi/obsidian/aily")
DIKIWI_VAULT = Path("/Users/luzi/obsidian/aily-dikiwi")
DIKIWI_DIR = AILY_VAULT / "DIKIWI"


def ensure_parallel_vault() -> None:
    DIKIWI_VAULT.mkdir(parents=True, exist_ok=True)
    readme = DIKIWI_VAULT / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Aily DIKIWI Vault\n\n"
            "This vault is the DIKIWI workshop and processing trace.\n"
            "Permanent notes belong in `/Users/luzi/obsidian/aily/3-Resources/Zettelkasten`.\n",
            encoding="utf-8",
        )


def move_dikiwi_directory() -> None:
    if not DIKIWI_DIR.exists():
        return
    target = DIKIWI_VAULT / "DIKIWI"
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(DIKIWI_DIR), str(target))


def normalize_zettelkasten_note(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return

    end = text.find("\n---\n", 4)
    if end == -1:
        return

    frontmatter = text[4:end]
    body = text[end + 5 :]

    title_match = re.search(r'^title:\s+"?(.*?)"?$', frontmatter, re.MULTILINE)
    title = title_match.group(1) if title_match else path.stem

    lines = frontmatter.splitlines()
    new_lines: list[str] = []
    tags: list[str] = []
    in_tags = False
    saw_note_type = False
    saw_aliases = False

    for line in lines:
        if line.startswith("tags:"):
            in_tags = True
            continue
        if in_tags:
            if line.startswith("  - "):
                tag = line[4:].strip()
                if tag and tag != "zettel" and tag not in tags:
                    tags.append(tag)
                continue
            in_tags = False

        if line.startswith("note_type:"):
            saw_note_type = True
            new_lines.append('note_type: "permanent"')
            continue
        if line.startswith("aliases:"):
            saw_aliases = True
            new_lines.append("aliases:")
            new_lines.append(f"  - {title}")
            continue
        if saw_aliases and line.startswith("  - "):
            continue

        new_lines.append(line)

    if not saw_aliases:
        insert_at = 2 if len(new_lines) >= 2 else len(new_lines)
        new_lines[insert_at:insert_at] = ["aliases:", f"  - {title}"]

    if not saw_note_type:
        insert_at = 2 if len(new_lines) >= 2 else len(new_lines)
        new_lines[insert_at:insert_at] = ['note_type: "permanent"']

    if tags:
        new_lines.append("tags:")
        for tag in tags:
            new_lines.append(f"  - {tag}")

    normalized = "---\n" + "\n".join(new_lines) + "\n---\n" + body
    path.write_text(normalized, encoding="utf-8")


def normalize_all_zettels() -> None:
    zk_root = AILY_VAULT / "3-Resources" / "Zettelkasten"
    for note in zk_root.rglob("*.md"):
        if note.name == "00 Zettelkasten Index.md":
            continue
        normalize_zettelkasten_note(note)


def rewrite_official_home() -> None:
    home = AILY_VAULT / "Home.md"
    if home.exists():
        text = home.read_text(encoding="utf-8")
        text = text.replace(
            "### Processing Layer\n- [[DIKIWI/00-Input/00-Input-MOC|DIKIWI Input]]\n- [[DIKIWI/01-Data/01-Data-MOC|DIKIWI Data]]\n- [[DIKIWI/06-Impact/06-Impact-MOC|DIKIWI Impact]]\n\n",
            "",
        )
        home.write_text(text, encoding="utf-8")


def main() -> None:
    ensure_parallel_vault()
    move_dikiwi_directory()
    normalize_all_zettels()
    rewrite_official_home()
    print(f"DIKIWI vault: {DIKIWI_VAULT}")
    print(f"Aily vault cleaned: {AILY_VAULT}")


if __name__ == "__main__":
    main()
