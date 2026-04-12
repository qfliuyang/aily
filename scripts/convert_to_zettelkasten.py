#!/usr/bin/env python3
"""Convert DIKIWI output to Zettelkasten format."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.writer.zettelkasten import ZettelkastenWriter


def main():
    # Load the test results
    audit_dir = Path("/Users/luzi/code/aily/dikiwi_audit_20260411_085043")
    results_path = audit_dir / "full_results.json"

    if not results_path.exists():
        print(f"Results not found: {results_path}")
        return

    with open(results_path, encoding="utf-8") as f:
        results = json.load(f)

    # Create Zettelkasten writer
    vault_path = "/Users/luzi/obsidian/aily/aily"
    writer = ZettelkastenWriter(vault_path, folder_name="Zettelkasten")

    print(f"Converting {len(results)} DIKIWI results to Zettelkasten...")

    # Convert each result
    all_ids = []
    for result in results:
        msg_num = result.get("message_num", 0)
        source = f"message_{msg_num}"

        ids = writer.add_from_dikiwi_result(result, source=source)
        all_ids.extend(ids)
        print(f"  Message {msg_num}: {len(ids)} zettels created")

    # Create topic MOCs
    writer.create_topic_mocs()

    # Print stats
    stats = writer.get_stats()
    print("\n" + "=" * 50)
    print("ZETTELKASTEN CREATED")
    print("=" * 50)
    print(f"Total zettels: {stats['total_zettels']}")
    print(f"Total tags: {stats['total_tags']}")
    print(f"Tags: {', '.join(stats['tags'][:10])}")
    print(f"\nLocation: {vault_path}/Zettelkasten/")
    print("\nKey features:")
    print("  - Luhmann IDs (1, 1a, 2, etc.)")
    print("  - Flat structure")
    print("  - Content-derived tags")
    print("  - Bidirectional links")
    print("  - Organic MOCs by topic")


if __name__ == "__main__":
    main()
