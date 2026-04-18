#!/usr/bin/env python3
"""Fix all existing vault notes: YAML frontmatter quoting, 01-Data filenames, and links."""

from __future__ import annotations

import re
from pathlib import Path

VAULT_PATH = Path("/Users/luzi/Documents/aily/aily")


def fix_frontmatter(filepath: Path) -> str | None:
    """Fix YAML frontmatter list items that contain brackets by quoting them.
    Returns new content or None if no fix needed."""
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None

    end_marker = text.find("\n---", 3)
    if end_marker == -1:
        return None

    fm_text = text[3:end_marker]
    body = text[end_marker + 4:]  # after \n---\n

    # Fix list items:  - [[foo]] or  - [[]] ->  - "[[foo]]"
    # Pattern: line starting with "  - " followed by unquoted content containing brackets
    fixed_fm = re.sub(
        r'^(  - )([^"\n\r]*\[\[.*\]\][^"\n\r]*)$',
        r'\1"\2"',
        fm_text,
        flags=re.MULTILINE,
    )

    # Also fix list items with bare brackets like  - [foo]  (single brackets)
    fixed_fm = re.sub(
        r'^(  - )([^"\n\r]*\[.*\][^"\n\r]*)$',
        r'\1"\2"',
        fixed_fm,
        flags=re.MULTILINE,
    )

    # Fix already-quoted nested lists from previous bad fix:
    #  - "[['information_c47d9ff1']]" -> "[[information_c47d9ff1]]"
    fixed_fm = re.sub(
        r'^(  - )"\[\[\'([^\']+)\'\]\]"$',
        r'\1"[[\2]]"',
        fixed_fm,
        flags=re.MULTILINE,
    )
    # Also fix unquoted nested lists:
    #  - [['information_c47d9ff1']] -> "[[information_c47d9ff1]]"
    fixed_fm = re.sub(
        r"^(  - )\[\['([^']+)'\]\]$",
        r'\1"[[\2]]"',
        fixed_fm,
        flags=re.MULTILINE,
    )

    if fixed_fm == fm_text:
        return None

    return "---" + fixed_fm + "\n---\n" + body


def fix_data_filename(old_path: Path) -> Path | None:
    """Rename old concatenated 01-Data filenames to underscore-separated."""
    name = old_path.name
    if not name.startswith("data-"):
        return None

    match = re.match(r"data-([a-zA-Z0-9-]*)-(\d+)\.md$", name)
    if not match:
        return None

    slug, idx = match.groups()

    # If slug already has underscores, it's already fixed
    if "_" in slug:
        return None

    # Remove leading/trailing dashes
    slug = slug.strip("-")
    if not slug:
        return None

    # Split camelCase / concatenated words
    new_slug = re.sub(r"([a-z])([A-Z])", r"\1_\2", slug)
    new_slug = re.sub(r"([a-zA-Z])(\d)", r"\1_\2", new_slug)
    new_slug = re.sub(r"(\d)([a-zA-Z])", r"\1_\2", new_slug)
    new_slug = new_slug.lower()

    while "__" in new_slug:
        new_slug = new_slug.replace("__", "_")

    new_name = f"data-{new_slug}-{idx}.md"
    if new_name == name:
        return None

    return old_path.parent / new_name


def main() -> None:
    fixed_count = 0
    renamed_count = 0

    # Fix frontmatter in all .md files
    for md_path in VAULT_PATH.rglob("*.md"):
        try:
            new_content = fix_frontmatter(md_path)
            if new_content:
                md_path.write_text(new_content, encoding="utf-8")
                fixed_count += 1
        except Exception as e:
            print(f"  [ERROR] {md_path.relative_to(VAULT_PATH)}: {e}")

    print(f"Fixed frontmatter in {fixed_count} files")

    # Rename old 01-Data files
    data_dir = VAULT_PATH / "01-Data"
    if data_dir.exists():
        rename_map: dict[Path, Path] = {}
        for subdir in data_dir.iterdir():
            if subdir.is_dir():
                for old_path in subdir.glob("data-*.md"):
                    new_path = fix_data_filename(old_path)
                    if new_path:
                        rename_map[old_path] = new_path

        for old_path, new_path in rename_map.items():
            try:
                old_path.rename(new_path)
                renamed_count += 1
            except Exception as e:
                print(f"  [ERROR] Rename {old_path.name}: {e}")

    print(f"Renamed {renamed_count} 01-Data files")
    print("Done.")


if __name__ == "__main__":
    main()
