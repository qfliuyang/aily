#!/usr/bin/env python3
"""Create Zettelkasten notes in Obsidian."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.config import SETTINGS
from aily.writer.obsidian import ObsidianWriter
from aily.queue.db import QueueDB


async def create_zettelkasten_notes():
    writer = ObsidianWriter(
        SETTINGS.obsidian_rest_api_key,
        SETTINGS.obsidian_vault_path,
        SETTINGS.obsidian_rest_api_port,
        queue_db=QueueDB(SETTINGS.queue_db_path)
    )

    notes = [
        {'title': 'CogniChip - AI Chip Design Startup', 'content': 'CogniChip is a startup focusing on AI-driven chip design to revolutionize the semiconductor industry.', 'tags': ['company', 'AI', 'semiconductor']},
        {'title': 'CogniChip ACI Platform - 75% Cost Reduction', 'content': "CogniChip's ACI platform aims to reduce chip design costs by 75% and development time by 50%.", 'tags': ['ACI', 'cost-reduction', 'time-efficiency']},
        {'title': 'CogniChip Founder - Faraj Aalaei', 'content': 'The company was founded by Faraj Aalaei, who has extensive experience in the semiconductor industry.', 'tags': ['founder', 'experience', 'semiconductor']},
        {'title': 'CogniChip Team - Industry Experts', 'content': 'CogniChip team includes experts from Amazon, Google, Apple, Synopsys, and academic institutions.', 'tags': ['team', 'experts', 'industry']},
        {'title': 'CogniChip Technology - Physical Constraints in AI', 'content': 'CogniChip technology involves embedding physical constraints into AI models for chip design.', 'tags': ['technology', 'AI', 'chip-design']},
        {'title': 'CogniChip Funding - $93M from NVIDIA and Intel', 'content': 'The company has raised over $93 million in funding, including investments from NVIDIA and Intel Capital.', 'tags': ['funding', 'investment', 'capital']},
        {'title': 'CogniChip Vision - Democratize Chip Design', 'content': 'CogniChip vision is to democratize chip design, making it accessible to a wider range of users.', 'tags': ['vision', 'democratization', 'chip-design']},
        {'title': 'CogniChip ACI - Full Automation', 'content': 'CogniChip ACI platform is designed to automate the entire chip design process.', 'tags': ['ACI', 'automation', 'chip-design']},
        {'title': 'CogniChip Timeline - 2026 Tape-out', 'content': 'The company plans to complete the tape-out of its first AI-designed chip by the end of 2026.', 'tags': ['tape-out', 'chip-design', 'planning']}
    ]

    created = []
    for note in notes:
        # Create note with Zettelkasten links
        tags_md = ' '.join([f'#[[{tag}]]' for tag in note['tags']])
        content = f"""{note['content']}

{tags_md}

---
Source: [[Kimi - CogniChip Deep Research]]
Date: 2026-04-09
"""
        try:
            path = await writer.write_note(note['title'], content, source_url='https://www.kimi.com/share/19d7012e-23d2-8df8-8000-00004c0aad17')
            created.append(path)
            print(f'Created: {path}')
        except Exception as e:
            print(f'Failed: {note["title"]} - {e}')

    print(f'\nCreated {len(created)} Zettelkasten notes in Obsidian!')
    return created


if __name__ == '__main__':
    asyncio.run(create_zettelkasten_notes())
