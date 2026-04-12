#!/usr/bin/env python3
"""Strip structural tags from the official Aily vault.

The official vault should use tags for content only. Shared note identity
such as "MOC", "index", "home", or "zettelkasten" belongs in properties.
"""

from __future__ import annotations

from pathlib import Path
import re


VAULT_ROOT = Path("/Users/luzi/obsidian/aily")
STRUCTURAL_TAGS = {"moc", "index", "home", "zettelkasten", "zettel"}


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 5 :]


def extract_inline_tags(frontmatter: str) -> list[str] | None:
    match = re.search(r"(?m)^tags:\s*\[(.*?)\]\s*$", frontmatter)
    if not match:
        return None
    raw = match.group(1).strip()
    if not raw:
        return []
    parts = [part.strip().strip('"').strip("'") for part in raw.split(",")]
    return [part for part in parts if part]


def replace_inline_tags(frontmatter: str, tags: list[str]) -> str:
    if tags:
        tags_line = f"tags: [{', '.join(_quote_tag(tag) for tag in tags)}]"
        return re.sub(r"(?m)^tags:\s*\[.*?\]\s*$", tags_line, frontmatter)
    return re.sub(r"(?m)^tags:\s*\[.*?\]\s*\n?", "", frontmatter)


def _quote_tag(tag: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", tag):
        return tag
    return f'"{tag}"'


def ensure_property(frontmatter: str, key: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(key)}:\s*.*$"
    line = f'{key}: "{value}"'
    if re.search(pattern, frontmatter):
        return re.sub(pattern, line, frontmatter)
    return f"{line}\n{frontmatter}".rstrip()


def normalize_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(original)
    if frontmatter is None:
        return False

    changed = False
    tags = extract_inline_tags(frontmatter)
    if tags is not None:
        kept = [tag for tag in tags if tag.lower() not in STRUCTURAL_TAGS]
        if kept != tags:
            frontmatter = replace_inline_tags(frontmatter, kept)
            changed = True

    role = None
    if path == VAULT_ROOT / "Home.md":
        role = "home"
    elif path == VAULT_ROOT / "3-Resources" / "Zettelkasten" / "00 Zettelkasten Index.md":
        role = "index"
        frontmatter = ensure_property(frontmatter, "index_scope", "zettelkasten")
        changed = True
    elif path == VAULT_ROOT / "3-Resources" / "MOCs" / "MOC-Index.md":
        role = "index"
        frontmatter = ensure_property(frontmatter, "index_scope", "mocs")
        changed = True
    elif path.parent == VAULT_ROOT / "3-Resources" / "MOCs":
        role = "moc"
    elif path == VAULT_ROOT / "1-Projects" / "1-Projects.md":
        role = "index"
        frontmatter = ensure_property(frontmatter, "index_scope", "projects")
        changed = True
    elif path == VAULT_ROOT / "2-Areas" / "2-Areas.md":
        role = "index"
        frontmatter = ensure_property(frontmatter, "index_scope", "areas")
        changed = True

    if role is not None:
        updated = ensure_property(frontmatter, "note_role", role)
        if updated != frontmatter:
            frontmatter = updated
            changed = True

    normalized = f"---\n{frontmatter.strip()}\n---\n{body.lstrip()}"
    if changed and normalized != original:
        path.write_text(normalized, encoding="utf-8")
        return True
    return False


def main() -> None:
    targets = [
        VAULT_ROOT / "Home.md",
        VAULT_ROOT / "1-Projects" / "1-Projects.md",
        VAULT_ROOT / "2-Areas" / "2-Areas.md",
        VAULT_ROOT / "3-Resources" / "Zettelkasten" / "00 Zettelkasten Index.md",
        VAULT_ROOT / "3-Resources" / "MOCs" / "MOC-Index.md",
    ]
    targets.extend(sorted((VAULT_ROOT / "3-Resources" / "MOCs").glob("*.md")))

    changed = 0
    for path in targets:
        if path.exists() and normalize_file(path):
            changed += 1

    print(f"Normalized {changed} official vault notes")


if __name__ == "__main__":
    main()
