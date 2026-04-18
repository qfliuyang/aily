"""DIKIWI Obsidian Integration - Full-Featured Knowledge System.

Leverages Obsidian's advanced features:
- Dataview: Query-able databases over markdown
- Canvas: Visual knowledge maps
- Templates: Structured note formats
- Graph View: Relationship visualization
- MOC: Maps of Content for navigation
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

# Import types from dikiwi_mind (main DIKIWI module)
# These are the actual types used in the pipeline
if TYPE_CHECKING:
    from aily.sessions.dikiwi_mind import DataPoint, InformationNode, Insight, Wisdom
else:
    # Define minimal type stubs for runtime
    DataPoint = Any
    InformationNode = Any
    Insight = Any
    Wisdom = Any

logger = logging.getLogger(__name__)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Remove empty/duplicate tags while keeping order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _slugify_title(title: str, max_length: int = 150) -> str:
    """Create a readable filesystem-safe slug. Uses underscores for spaces."""
    cleaned = "".join(c for c in str(title) if c.isalnum() or c in " -_").strip()
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return "Untitled"
    cleaned = cleaned.replace(" ", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned[:max_length].rstrip("_")


class DikiwiObsidianWriter:
    """Full-featured Obsidian integration for DIKIWI knowledge system.

    Creates a hierarchical, query-able, visual knowledge structure:
    00-Chaos/           # Raw captured inputs
    01-Data/            # Extracted facts (Dataview)
    02-Information/     # Classified nodes (MOC)
    03-Knowledge/       # Relationships (Graph)
    04-Insight/         # Patterns (Dashboards)
    05-Wisdom/          # Principles (Library)
    06-Impact/          # Actions (Tasks)
    07-Proposal/        # Reactor-Residual proposals
    08-Entrepreneurship/# Reviewed business plans
    """

    STAGE_NAMES = {
        0: "00-Chaos",
        1: "01-Data",
        2: "02-Information",
        3: "03-Knowledge",
        4: "04-Insight",
        5: "05-Wisdom",
        6: "06-Impact",
    }

    LEVEL_TO_FOLDER = {
        "chaos": "00-Chaos",
        "data": "01-Data",
        "information": "02-Information",
        "knowledge": "03-Knowledge",
        "insight": "04-Insight",
        "wisdom": "05-Wisdom",
        "impact": "06-Impact",
    }

    def __init__(
        self,
        vault_path: str | Path,
        folder_prefix: str = "",
        zettelkasten_only: bool = True,
    ) -> None:
        self.vault_path = Path(vault_path)
        self.dikiwi_root = self.vault_path / folder_prefix if folder_prefix else self.vault_path
        self.zettelkasten_maps_root = self.vault_path / "99-MOC"
        self.zettelkasten_only = zettelkasten_only
        self._id_to_title: dict[str, str] = {}
        self._ensure_zettelkasten_structure()

        if not self.zettelkasten_only:
            self._ensure_structure()
            logger.info("DikiwiObsidianWriter initialized at %s", self.dikiwi_root)
        else:
            logger.info("DikiwiObsidianWriter initialized (Zettelkasten-only mode)")

    def register_note_title(self, dikiwi_id: str, title: str) -> None:
        """Register a note title so _make_link can build full-filename wikilinks."""
        self._id_to_title[dikiwi_id] = _slugify_title(title, max_length=200)

    def _ensure_zettelkasten_structure(self) -> None:
        """Create the flat numbered directories for the DIKIWI Zettelkasten."""
        for stage_name in self.STAGE_NAMES.values():
            (self.vault_path / stage_name).mkdir(parents=True, exist_ok=True)
        (self.vault_path / "07-Proposal").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "08-Entrepreneurship").mkdir(parents=True, exist_ok=True)
        (self.vault_path / "99-MOC").mkdir(parents=True, exist_ok=True)

        index_path = self.vault_path / "00-Chaos" / "00 Zettelkasten Index.md"
        if not index_path.exists():
            index_path.write_text(self._build_zettelkasten_index(), encoding="utf-8")

    def _build_zettelkasten_index(self) -> str:
        """Create the main Obsidian-facing index for permanent notes."""
        return """---
note_role: "index"
index_scope: "zettelkasten"
---

# Zettelkasten Index

Permanent notes produced by DIKIWI live here. Browse by recency, tags, or Maps of Content.

## Recent Notes
```dataview
TABLE dikiwi_level, dikiwi_id, date_created, source
FROM "/"
WHERE note_type = "permanent" AND file.name != "00 Zettelkasten Index"
SORT date_created DESC
LIMIT 50
```

## By Level
```dataview
TABLE length(rows) as Notes
FROM "/"
WHERE note_type = "permanent" AND dikiwi_level
GROUP BY dikiwi_level
SORT dikiwi_level ASC
```

## Maps Of Content
```dataview
LIST
FROM "99-MOC"
SORT file.name ASC
```

## Tag Clusters
```dataview
TABLE length(rows) as Notes
FROM "/"
WHERE note_type = "permanent"
FLATTEN tags AS tag
GROUP BY tag
SORT length(rows) DESC
```
"""

    def _build_topic_map(self, tag: str) -> str:
        """Create a simple Map of Content for a tag cluster."""
        return f"""---
note_role: "moc"
topic: "{tag}"
tags:
  - {tag}
---

# {tag}

## Notes
```dataview
TABLE date_created, source
FROM "/"
WHERE note_type = "permanent" AND contains(tags, "{tag}")
SORT date_created DESC
```
"""

    def _sanitize_map_name(self, tag: str) -> str:
        """Make a filesystem-safe MOC filename from a tag."""
        safe = "".join(c if c.isalnum() or c in " -_" else "-" for c in tag).strip()
        return safe.replace(" ", "-") or "untagged"

    def _update_topic_maps(self, tags: list[str]) -> None:
        """Keep simple topic MOCs available for Obsidian navigation."""
        for tag in tags:
            tag = str(tag).strip()
            if not tag or tag == "zettel":
                continue
            map_path = self.zettelkasten_maps_root / f"{self._sanitize_map_name(tag)}.md"
            map_path.write_text(self._build_topic_map(tag), encoding="utf-8")

    def _ensure_structure(self) -> None:
        """Create full DIKIWI folder structure with MOC files."""
        # Stage folders
        for stage_num, stage_name in self.STAGE_NAMES.items():
            stage_dir = self.dikiwi_root / stage_name
            stage_dir.mkdir(parents=True, exist_ok=True)

            # Create MOC file for each stage
            moc_path = stage_dir / f"{stage_name}-MOC.md"
            if not moc_path.exists():
                moc_content = self._generate_moc_template(stage_num, stage_name)
                moc_path.write_text(moc_content, encoding="utf-8")

        # Support folders
        for folder in ["Canvas", "Templates", "_System"]:
            (self.dikiwi_root / folder).mkdir(parents=True, exist_ok=True)

        # Create templates
        self._create_templates()

        # Create overview canvas
        self._create_overview_canvas()

        logger.info("DIKIWI structure ensured with MOCs and templates")

    def _generate_moc_template(self, stage_num: int, stage_name: str) -> str:
        """Generate Map of Content for each stage."""
        stage_type = stage_name.split("-")[1]

        templates = {
            0: """---
tags: [MOC, dikiwi, input, inbox]
---

# Input MOC

## Recent Inputs
```dataview
TABLE source, date_created
FROM "00-Chaos"
WHERE file.name != "00-Chaos-MOC"
SORT date_created DESC
LIMIT 20
```

## By Source
```dataview
TABLE length(rows) as Count
FROM "00-Chaos"
GROUP BY source
```

## Navigation
- [[01-Data/01-Data-MOC|Data Stage →]]
""",
            1: """---
tags: [MOC, dikiwi, data]
---

# Data MOC

## Recent Data Points
```dataview
TABLE data_type, confidence, source
FROM "01-Data"
WHERE file.name != "01-Data-MOC"
SORT date_created DESC
LIMIT 20
```

## By Type
```dataview
LIST
FROM "01-Data"
WHERE data_type
GROUP BY data_type
```

## High Confidence Data
```dataview
LIST
FROM "01-Data"
WHERE confidence >= 0.9
SORT confidence DESC
```

## Navigation
- [[00-Chaos/00-Chaos-MOC|← Input]]
- [[02-Information/02-Information-MOC|Information →]]
""",
            2: """---
tags: [MOC, dikiwi, information]
---

# Information MOC

## Recent Nodes
```dataview
TABLE domain, info_type, confidence
FROM "02-Information"
WHERE file.name != "02-Information-MOC"
SORT date_created DESC
LIMIT 20
```

## By Domain
```dataview
LIST
FROM "02-Information"
WHERE domain
GROUP BY domain
```

## By Type
```dataview
TABLE length(rows) as Count
FROM "02-Information"
WHERE info_type
GROUP BY info_type
```

## Navigation
- [[01-Data/01-Data-MOC|← Data]]
- [[03-Knowledge/03-Knowledge-MOC|Knowledge →]]
""",
            3: """---
tags: [MOC, dikiwi, knowledge, links]
---

# Knowledge MOC

## Recent Links
```dataview
TABLE relation_type, strength
FROM "03-Knowledge"
WHERE file.name != "03-Knowledge-MOC"
SORT date_created DESC
LIMIT 20
```

## Relationship Types
```dataview
TABLE length(rows) as Count
FROM "03-Knowledge"
WHERE relation_type
GROUP BY relation_type
```

## Strong Connections (≥0.8)
```dataview
LIST
FROM "03-Knowledge"
WHERE strength >= 0.8
SORT strength DESC
```

## Navigation
- [[02-Information/02-Information-MOC|← Information]]
- [[04-Insight/04-Insight-MOC|Insights →]]
""",
            4: """---
tags: [MOC, dikiwi, insights, dashboard]
---

# Insights MOC

## Recent Insights
```dataview
TABLE insight_type, confidence, source_message
FROM "04-Insight"
WHERE file.name != "04-Insight-MOC"
SORT date_created DESC
LIMIT 20
```

## By Type
### Themes
```dataview
LIST confidence
FROM "04-Insight"
WHERE insight_type = "theme"
SORT confidence DESC
```

### Patterns
```dataview
LIST confidence
FROM "04-Insight"
WHERE insight_type = "pattern"
SORT confidence DESC
```

### Opportunities
```dataview
LIST confidence
FROM "04-Insight"
WHERE insight_type = "opportunity"
SORT confidence DESC
```

### Gaps
```dataview
LIST confidence
FROM "04-Insight"
WHERE insight_type = "gap"
SORT confidence DESC
```

## High Confidence Insights
```dataview
LIST
FROM "04-Insight"
WHERE confidence >= 0.8
SORT confidence DESC
```

## Dashboard
→ [[04-Insight/Insight-Dashboard|View Dashboard]]

## Navigation
- [[03-Knowledge/03-Knowledge-MOC|← Knowledge]]
- [[05-Wisdom/05-Wisdom-MOC|Wisdom →]]
""",
            5: """---
tags: [MOC, dikiwi, wisdom, principles]
---

# Wisdom MOC

## Principles Library
```dataview
TABLE confidence, supporting_insights
FROM "05-Wisdom"
WHERE file.name != "05-Wisdom-MOC"
SORT confidence DESC
```

## By Domain
```dataview
LIST
FROM "05-Wisdom"
WHERE applicable_domain
GROUP BY applicable_domain
```

## Actionable Principles
```dataview
LIST
FROM "05-Wisdom"
WHERE actionable = true
SORT confidence DESC
```

## Navigation
- [[04-Insight/04-Insight-MOC|← Insights]]
- [[06-Impact/06-Impact-MOC|Impact →]]
""",
            6: """---
tags: [MOC, dikiwi, impact, proposals, tasks]
---

# Impact MOC

## Active Proposals
```dataview
TABLE proposal_type, priority, due_date
FROM "06-Impact"
WHERE status = "active"
SORT priority DESC
```

## Tasks
```tasks
not done
path includes 06-Impact
```

## By Type
```dataview
TABLE length(rows) as Count
FROM "06-Impact"
WHERE proposal_type
GROUP BY proposal_type
```

## Navigation
- [[05-Wisdom/05-Wisdom-MOC|← Wisdom]]
- [[Canvas/DIKIWI-Overview|View Overview Canvas]]
""",
        }

        return templates.get(stage_num, f"# {stage_name} MOC\n")

    def _create_templates(self) -> None:
        """Create note templates for each stage."""
        templates_dir = self.dikiwi_root / "Templates"

        # Data template
        data_template = """---
dikiwi_stage: "data"
pipeline_id: "{{pipeline_id}}"
data_point_id: "{{data_point_id}}"
source: "{{source}}"
source_url: "{{source_url}}"
date_created: "{{date_created}}"
confidence: {{confidence}}
data_type: "{{data_type}}"
tags: ["dikiwi", "data", "{{source}}"]
---

# {{title}}

{{content}}

---

## Metadata
- **Source**: {{source}}
- **Confidence**: {{confidence}}%
- **Type**: {{data_type}}
- **Extracted**: {{date_created}}

## Related
- [[01-Data/01-Data-MOC|Data Index]]
- Next Stage: [[02-Information/02-Information-MOC|Information]]
"""
        (templates_dir / "Data-Template.md").write_text(data_template, encoding="utf-8")

        # Insight template
        insight_template = """---
dikiwi_stage: "insight"
insight_id: "{{insight_id}}"
insight_type: "{{insight_type}}"
confidence: {{confidence}}
source_message: "[[{{source_message}}|{{source_title}}]]"
date_created: "{{date_created}}"
tags: ["dikiwi", "insight", "{{insight_type}}"]
parent_theme: "{{parent_theme}}"
related_domains: [{{domains}}]
---

# {{insight_type}}: {{title}}

{{description}}

---

## Analysis
- **Confidence**: `{{confidence}}`
- **Type**: #{{insight_type}}
- **Source**: [[{{source_message}}]]
- **Theme**: {{parent_theme}}

## Evidence
{{supporting_evidence}}

## Actionable Implications
{{implications}}

---

## Related Insights
```dataview
TABLE insight_type, confidence, date_created
FROM "04-Insight"
WHERE insight_type = this.insight_type AND confidence > 0.7
SORT confidence DESC
LIMIT 10
```

## Connections
- [[05-Wisdom/05-Wisdom-MOC|Wisdom Stage]]
- [[04-Insight/Insight-Dashboard|Dashboard]]
"""
        (templates_dir / "Insight-Template.md").write_text(insight_template, encoding="utf-8")

    def _create_overview_canvas(self) -> None:
        """Create the main DIKIWI overview canvas."""
        canvas_path = self.dikiwi_root / "Canvas" / "DIKIWI-Overview.canvas"

        canvas_data = {
            "nodes": [
                {
                    "id": "input",
                    "type": "text",
                    "text": "# 00-Chaos\n\n📥 Raw captures\n\n[[00-Chaos/00-Chaos-MOC|View All]]",
                    "x": 0,
                    "y": 0,
                    "width": 220,
                    "height": 160,
                    "color": "1"  # Red
                },
                {
                    "id": "data",
                    "type": "text",
                    "text": "# 01-Data\n\n📊 Extracted facts\n\n[[01-Data/01-Data-MOC|View All]]",
                    "x": 350,
                    "y": 0,
                    "width": 220,
                    "height": 160,
                    "color": "2"  # Orange
                },
                {
                    "id": "information",
                    "type": "text",
                    "text": "# 02-Information\n\n📝 Classified nodes\n\n[[02-Information/02-Information-MOC|View All]]",
                    "x": 700,
                    "y": 0,
                    "width": 220,
                    "height": 160,
                    "color": "3"  # Yellow
                },
                {
                    "id": "knowledge",
                    "type": "text",
                    "text": "# 03-Knowledge\n\n🔗 Linked network\n\n[[03-Knowledge/03-Knowledge-MOC|View All]]",
                    "x": 1050,
                    "y": 0,
                    "width": 220,
                    "height": 160,
                    "color": "4"  # Green
                },
                {
                    "id": "insights",
                    "type": "text",
                    "text": "# 04-Insight\n\n💡 Pattern detection\n\n[[04-Insight/04-Insight-MOC|View All]]\n\n[[04-Insight/Insight-Dashboard|📊 Dashboard]]",
                    "x": 700,
                    "y": 350,
                    "width": 220,
                    "height": 180,
                    "color": "5"  # Blue
                },
                {
                    "id": "wisdom",
                    "type": "text",
                    "text": "# 05-Wisdom\n\n🧠 Synthesized principles\n\n[[05-Wisdom/05-Wisdom-MOC|View All]]",
                    "x": 350,
                    "y": 350,
                    "width": 220,
                    "height": 160,
                    "color": "6"  # Purple
                },
                {
                    "id": "impact",
                    "type": "text",
                    "text": "# 06-Impact\n\n🚀 Actionable proposals\n\n[[06-Impact/06-Impact-MOC|View All]]",
                    "x": 0,
                    "y": 350,
                    "width": 220,
                    "height": 160,
                    "color": "7"  # Pink
                }
            ],
            "edges": [
                {"id": "e1", "fromNode": "input", "fromSide": "right", "toNode": "data", "toSide": "left"},
                {"id": "e2", "fromNode": "data", "fromSide": "right", "toNode": "information", "toSide": "left"},
                {"id": "e3", "fromNode": "information", "fromSide": "right", "toNode": "knowledge", "toSide": "left"},
                {"id": "e4", "fromNode": "knowledge", "fromSide": "bottom", "toNode": "insights", "toSide": "top"},
                {"id": "e5", "fromNode": "insights", "fromSide": "left", "toNode": "wisdom", "toSide": "right"},
                {"id": "e6", "fromNode": "wisdom", "fromSide": "left", "toNode": "impact", "toSide": "right"}
            ]
        }

        canvas_path.write_text(json.dumps(canvas_data, indent=2), encoding="utf-8")

    def _get_day_dir(self, stage: str) -> Path:
        """Get or create day-based directory for a stage."""
        now = datetime.now().astimezone()
        day_dir = self.dikiwi_root / stage / f"{now.year}-{now.month:02d}-{now.day:02d}"
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def _format_frontmatter(self, data: dict[str, Any]) -> str:
        """Format dict as YAML frontmatter."""
        lines = ["---"]
        for key, value in data.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    if isinstance(item, str):
                        escaped = item.replace('"', '\\"')
                        lines.append(f'  - "{escaped}"')
                    else:
                        lines.append(f"  - {item}")
            elif isinstance(value, str):
                # Escape quotes in strings
                escaped = value.replace('"', '\\"')
                lines.append(f'{key}: "{escaped}"')
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def _title_short(text: str, fallback: str = "Untitled", max_len: int = 80) -> str:
        cleaned = " ".join(str(text).replace("\n", " ").split()).strip(" -:")
        if not cleaned:
            return fallback
        sentence = cleaned.split(".")[0].strip()
        candidate = sentence if 8 <= len(sentence) <= max_len else cleaned
        if len(candidate) <= max_len:
            return candidate
        # Truncate at last word boundary, add ellipsis if truncated
        truncated = candidate[:max_len].rsplit(" ", 1)[0].rstrip(" -:")
        return (truncated or fallback)

    @staticmethod
    def _extract_chunk_title(cleaned_chunk: str, chunk_index: int, max_len: int = 60) -> str:
        """Extract a meaningful title from raw chunk content.

        Prefers markdown headings, then the first meaningful sentence.
        Falls back to 'Data Chunk N' if nothing usable is found.
        """
        import re

        def _is_meaningful(line: str) -> bool:
            """Reject single-word ALL CAPS, bare numbers, short fragments, and slide junk."""
            text = line.strip()
            if not text or len(text) < 4:
                return False
            words = text.split()
            if len(words) < 3:
                return False
            # Reject lines that are mostly ALL CAPS (e.g. "WORKER3", "P1", "FIGURE 1")
            if all(w.isupper() and len(w) <= 8 for w in words):
                return False
            # Reject lines with very short average word length (fragments like "e 6nus snug")
            avg_word_len = sum(len(w) for w in words) / len(words)
            if avg_word_len < 2.5:
                return False
            # Reject lines that are just bullet markers or image placeholders
            if text in ("•", "-", "*", "<!-- image -->"):
                return False
            # Reject HTML comments
            if text.startswith("<!--") and text.endswith("-->"):
                return False
            return True

        # Generic headings that offer no semantic value — skip them
        GENERIC_HEADINGS = {
            "outline", "summary", "agenda", "contents", "table of contents",
            "introduction", "conclusion", "future work", "references",
            "acknowledgements", "thank you", "questions", "overview",
            "background", "motivation", "related work", "results",
            "discussion", "appendix", "notes", "details",
        }

        # 1. Look for a markdown heading (scan all lines — presentations often
        # have title slides / logos before the first real heading)
        for line in cleaned_chunk.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if len(title) >= 3 and title.lower() not in GENERIC_HEADINGS:
                    return title if len(title) <= max_len else title[:max_len].rsplit(" ", 1)[0].rstrip(" -:")

        # 2. Find first meaningful sentence across all lines
        for line in cleaned_chunk.splitlines():
            if _is_meaningful(line):
                candidate = " ".join(line.split())
                if len(candidate) <= max_len:
                    return candidate
                return candidate[:max_len].rsplit(" ", 1)[0].rstrip(" -:")

        # 3. Fallback
        return f"Data Chunk {chunk_index}"

    def _make_link(self, note_id: str, display: str | None = None) -> str:
        """Build an Obsidian wikilink that resolves by filename.

        Uses the full ``{id}-{title}`` filename so links work immediately
        without waiting for Obsidian's alias index.
        """
        safe_title = self._id_to_title.get(note_id, "")
        if safe_title:
            target = f"{note_id}-{safe_title}"
        else:
            target = note_id
        if display and display != target:
            return f"[[{target}|{display}]]"
        return f"[[{target}]]"

    def _write_dikiwi_note(
        self,
        stage_folder: str,
        dikiwi_id: str,
        title: str,
        frontmatter: dict[str, Any],
        body: str,
        source_paths: list[str] | None = None,
        h1_title: str | None = None,
    ) -> str:
        """Write a note to a DIKIWI stage folder. Returns dikiwi_id for linking."""
        day_dir = self._get_day_dir(stage_folder)
        safe_title = _slugify_title(title)
        self._id_to_title[dikiwi_id] = safe_title
        filename = f"{dikiwi_id}-{safe_title}.md"
        path = day_dir / filename

        fm: dict[str, Any] = {
            "dikiwi_id": dikiwi_id,
            "aliases": [dikiwi_id],
            "date_created": datetime.now().astimezone().isoformat(),
        }
        fm.update(frontmatter)
        if source_paths:
            fm["source_paths"] = _dedupe_preserve_order([str(p) for p in source_paths])

        heading = h1_title if h1_title else title
        note_content = f"{self._format_frontmatter(fm)}\n\n# {heading}\n\n{body}\n"
        path.write_text(note_content, encoding="utf-8")
        logger.info("Wrote DIKIWI note: %s", filename)
        return dikiwi_id

    async def write_data_note(
        self,
        drop: Any,
        pipeline_id: str,
        source_paths: list[str] | None = None,
        title: str = "",
        summary: str = "",
        concepts: list[str] | None = None,
    ) -> str:
        """Write DATA stage note as an organized document summary. Returns dikiwi_id."""
        source = getattr(drop, "source", "unknown")
        content = getattr(drop, "content", "")

        dikiwi_id = f"data_{hashlib.sha1(source.encode()).hexdigest()[:8]}"
        note_title = title or self._title_short(source, fallback="Source Data")

        fm: dict[str, Any] = {
            "type": "data",
            "source": source,
            "content_chars": len(content),
            "tags": ["data"],
        }

        body_parts: list[str] = []
        if summary:
            body_parts.append(summary)
            body_parts.append("")

        if concepts:
            body_parts.append("## Extracted Concepts")
            for c in concepts:
                body_parts.append(f"- {c}")
            body_parts.append("")

        body_parts.append("## Source")
        body_parts.append(f"- `{source}`")
        body_parts.append(f"- {len(content):,} characters processed")

        body = "\n".join(body_parts)
        return self._write_dikiwi_note("01-Data", dikiwi_id, note_title, fm, body, source_paths)

    async def write_information_note(
        self,
        node: Any,
        data_note_id: str,
        source: str,
        source_paths: list[str] | None = None,
        data_point_id: str = "",
    ) -> str:
        """Write INFORMATION stage note for one classified idea chunk. Returns dikiwi_id."""
        nid = getattr(node, "id", "")
        content = getattr(node, "content", "")
        domain = getattr(node, "domain", "general")
        info_type = getattr(node, "info_type", "fact")
        tags = list(getattr(node, "tags", []))
        confidence = float(getattr(node, "confidence", 0.8) if hasattr(node, "confidence") else 0.8)

        dikiwi_id = f"information_{hashlib.sha1(nid.encode()).hexdigest()[:8]}"
        title = self._title_short(content, fallback=f"{domain.title()} Concept")

        fm: dict[str, Any] = {
            "type": "information",
            "domain": domain,
            "info_type": info_type,
            "confidence": round(confidence, 2),
            "tags": _dedupe_preserve_order(["information", domain] + tags),
        }
        if data_note_id:
            fm["source"] = self._make_link(data_note_id)
        if data_point_id:
            fm["data_point_id"] = data_point_id
        body_lines = [
            content,
            "",
            "## Classification",
            f"- Domain: {domain}",
            f"- Type: {info_type}",
            f"- Confidence: {confidence:.0%}",
        ]
        if data_note_id:
            body_lines.append(f"- From: {self._make_link(data_note_id)}")
        body = "\n".join(body_lines)

        return self._write_dikiwi_note("02-Information", dikiwi_id, title, fm, body, source_paths)

    async def write_knowledge_note(
        self,
        link: Any,
        src_node: Any,
        tgt_node: Any,
        src_info_id: str,
        tgt_info_id: str,
        source: str,
    ) -> str:
        """Write KNOWLEDGE stage note recording a meaningful relationship. Returns dikiwi_id."""
        src_id = getattr(link, "source_id", "")
        tgt_id = getattr(link, "target_id", "")
        relation = getattr(link, "relation_type", "relates_to")
        strength = float(getattr(link, "strength", 0.5))
        reasoning = getattr(link, "reasoning", "")

        src_content = getattr(src_node, "content", "")
        tgt_content = getattr(tgt_node, "content", "")

        dikiwi_id = f"knowledge_{hashlib.sha1((src_id + tgt_id).encode()).hexdigest()[:8]}"
        src_title = self._title_short(src_content, "Src", max_len=25)
        tgt_title = self._title_short(tgt_content, "Tgt", max_len=25)
        rel_short = relation.replace("_", " ")
        title = f"{src_title} → {rel_short} → {tgt_title}"

        nodes_list = [self._make_link(src_info_id), self._make_link(tgt_info_id)] if src_info_id and tgt_info_id else []

        fm: dict[str, Any] = {
            "type": "knowledge",
            "nodes": nodes_list,
            "relation": relation,
            "strength": round(strength, 2),
            "tags": ["knowledge", relation],
        }
        body_lines: list[str] = []
        if reasoning:
            body_lines += [reasoning, ""]
        body_lines += [
            "## Connected Ideas",
            f"**A**: {src_content}",
            "",
            f"**{relation.replace('_', ' ').title()}**",
            "",
            f"**B**: {tgt_content}",
        ]
        if nodes_list:
            body_lines += ["", "## Related", *[f"- {n}" for n in nodes_list]]

        return self._write_dikiwi_note("03-Knowledge", dikiwi_id, title, fm, "\n".join(body_lines))

    async def write_insight_note(
        self,
        insight: Any,
        knowledge_note_ids: list[str],
        drop: Any,
        source_paths: list[str] | None = None,
    ) -> str:
        """Write INSIGHT stage note for an emergent pattern. Returns dikiwi_id."""
        insight_id = getattr(insight, "id", "")
        description = getattr(insight, "description", "")
        insight_type = getattr(insight, "insight_type", "pattern")
        confidence = float(getattr(insight, "confidence", 0.5))

        dikiwi_id = f"insight_{hashlib.sha1(insight_id.encode()).hexdigest()[:8]}"
        title = self._title_short(description, f"{insight_type.title()} Insight")

        from_knowledge = [self._make_link(k) for k in knowledge_note_ids if k]
        fm: dict[str, Any] = {
            "type": "insight",
            "from_knowledge": from_knowledge,
            "insight_type": insight_type,
            "confidence": round(confidence, 2),
            "tags": _dedupe_preserve_order(["insight", insight_type]),
        }
        body = "\n".join([
            description,
            "",
            "## Type",
            f"- insight_type: {insight_type}",
            f"- confidence: {confidence:.0%}",
            "",
            "## Source Knowledge",
            *(([f"- {k}" for k in from_knowledge]) or ["- *(no linked knowledge notes)*"]),
        ])

        return self._write_dikiwi_note("04-Insight", dikiwi_id, title, fm, body, source_paths)

    async def write_wisdom_note(
        self,
        zettel: Any,
        insight_note_ids: list[str],
        drop: Any,
        source_paths: list[str] | None = None,
        link_map: dict[str, str] | None = None,
    ) -> str:
        """Write WISDOM stage permanent note with grounded_in links. Returns dikiwi_id."""
        zettel_id_base = getattr(zettel, "id", hashlib.sha1(str(zettel).encode()).hexdigest()[:6])
        title = getattr(zettel, "title", "Untitled")
        content = getattr(zettel, "content", "")
        tags = list(getattr(zettel, "tags", []))
        links_to = list(getattr(zettel, "links_to", []))
        confidence = float(getattr(zettel, "confidence", 0.5))
        source = getattr(drop, "source", "")

        dikiwi_id = f"wisdom_{zettel_id_base}"
        deduped_tags = _dedupe_preserve_order(["wisdom"] + tags)

        zettel_dir = self._get_day_dir("05-Wisdom")
        safe_title = _slugify_title(title, max_length=200)
        self._id_to_title[dikiwi_id] = safe_title
        filename = f"{dikiwi_id}-{safe_title}.md"
        path = zettel_dir / filename

        grounded_in = [self._make_link(iid) for iid in insight_note_ids if iid]

        fm: dict[str, Any] = {
            "type": "wisdom",
            "dikiwi_id": dikiwi_id,
            "aliases": [dikiwi_id],
            "title": title,
            "source": source,
            "date_created": datetime.now().astimezone().isoformat(),
            "note_type": "permanent",
            "dikiwi_level": "wisdom",
            "word_count": len(content.split()),
            "confidence": round(confidence, 2),
            "grounded_in": grounded_in,
            "tags": deduped_tags,
        }
        if source_paths:
            fm["source_paths"] = _dedupe_preserve_order([str(p) for p in source_paths])

        body_lines: list[str] = [
            self._format_frontmatter(fm), "",
            f"# {title}", "",
            content, "",
        ]
        if links_to:
            body_lines += ["## Related", ""]
            for link in links_to:
                link_lower = link.lower()
                matched_id = link_map.get(link_lower) if link_map else None
                if not matched_id and link_map:
                    # Fuzzy fallback: substring match against map keys
                    for key, zid in link_map.items():
                        if link_lower in key or key in link_lower:
                            matched_id = zid
                            break
                if matched_id:
                    body_lines.append(f"- {self._make_link(matched_id, link)}")
                # Skip unresolved conceptual links to avoid broken wiki-links in the vault
            body_lines.append("")
        if grounded_in:
            body_lines += ["## Grounded In", "", *[f"- {g}" for g in grounded_in], ""]
        body_lines += ["---", "", f"*Source: {source}*"]

        path.write_text("\n".join(body_lines), encoding="utf-8")
        self._update_topic_maps(tags)
        logger.info("Wrote wisdom note: %s (%d words)", filename, len(content.split()))
        return dikiwi_id

    async def write_impact_note(
        self,
        impact: dict[str, Any],
        wisdom_note_ids: list[str],
        drop: Any,
        source_paths: list[str] | None = None,
    ) -> str:
        """Write IMPACT stage action note. Returns dikiwi_id."""
        description = impact.get("description", "")
        impact_type = impact.get("type", "action")
        priority = impact.get("priority", "medium")
        effort = impact.get("effort_estimate", "medium")
        rationale = impact.get("rationale", "")

        dikiwi_id = f"impact_{hashlib.sha1(description[:50].encode()).hexdigest()[:8]}"
        title = self._title_short(description, "Action Item")

        based_on = [self._make_link(wid) for wid in wisdom_note_ids if wid]
        fm: dict[str, Any] = {
            "type": "impact",
            "based_on": based_on,
            "impact_type": impact_type,
            "priority": priority,
            "effort": effort,
            "status": "pending",
            "tags": _dedupe_preserve_order(["impact", impact_type, priority]),
        }
        body = "\n".join([
            description, "",
            "## Rationale",
            rationale or "*(no rationale provided)*", "",
            "## Based On",
            *(([f"- {b}" for b in based_on]) or ["- *(no linked wisdom notes)*"]), "",
            "## Task",
            f"- [ ] {description}",
        ])

        return self._write_dikiwi_note("06-Impact", dikiwi_id, title, fm, body, source_paths, h1_title=description)

    async def write_input(self, message_id: str, content: str, source: str) -> Path | None:
        """Write raw input to 00-Chaos."""
        if self.zettelkasten_only:
            return None

        day_dir = self._get_day_dir("00-Chaos")
        note_path = day_dir / f"{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-{message_id}.md"

        frontmatter = {
            "dikiwi_stage": "input",
            "message_id": message_id,
            "source": source,
            "date_created": datetime.now().astimezone().isoformat(),
            "tags": ["dikiwi", "input", source],
        }

        content = f"{self._format_frontmatter(frontmatter)}\n\n# Input: {message_id[:8]}\n\n{content}\n"

        note_path.write_text(content, encoding="utf-8")
        logger.info("Wrote input: %s", note_path)
        return note_path

    async def write_note(
        self,
        title: str,
        markdown: str,
        source_url: str = "",
    ) -> str:
        """Write a generic note to the vault (compatible with ObsidianWriter interface)."""
        safe_title = _slugify_title(title).replace("/", "_").replace("..", "_")[:120]

        # Route entrepreneur notes to dedicated folder
        if source_url and source_url.startswith("aily://entrepreneur"):
            note_dir = self._get_day_dir("08-Entrepreneurship")
        else:
            note_dir = self.vault_path
        path = note_dir / f"{safe_title}.md"

        if source_url:
            frontmatter = {
                "title": title,
                "source_url": source_url,
                "date_created": datetime.now().astimezone().isoformat(),
            }
            content = f"{self._format_frontmatter(frontmatter)}\n\n{markdown}\n"
        else:
            content = markdown

        path.write_text(content, encoding="utf-8")
        logger.info("Wrote note: %s", path)
        return str(path)

    async def write_data_points(
        self,
        message_id: str,
        data_points: list[DataPoint],
        source: str,
    ) -> list[Path]:
        """Write data points to 01-Data with Dataview metadata."""
        day_dir = self._get_day_dir("01-Data")
        paths = []

        for i, dp in enumerate(data_points):
            concept = getattr(dp, "concept", "") or ""
            content = getattr(dp, "content", "") or ""
            base = concept.strip() or content.strip()
            words = base.split()[:6]
            slug = "_".join(words).lower()[:40].rstrip("_")
            if not slug:
                slug = f"dp-{i}"
            safe_dp_id = f"{slug}-{i}"
            note_path = day_dir / f"data-{safe_dp_id}.md"

            frontmatter = {
                "dikiwi_stage": "data",
                "pipeline_id": message_id,
                "data_point_index": i,
                "source": source,
                "date_created": datetime.now().astimezone().isoformat(),
                "confidence": round(float(getattr(dp, "confidence", 0.8)), 2),
                "data_type": getattr(dp, "concept", "") or "fact",
                "tags": ["dikiwi", "data", source],
            }

            content_lines = [
                self._format_frontmatter(frontmatter),
                f"",
                f"# Data Point {i}",
                f"",
                f"{getattr(dp, 'content', '')}",
                f"",
                f"---",
                f"",
                f"## Metadata",
                f"- **Confidence**: {float(getattr(dp, 'confidence', 0.8)):.0%}",
                f"- **Source**: {source}",
            ]

            note_path.write_text("\n".join(content_lines), encoding="utf-8")
            paths.append(note_path)

        logger.info("Wrote %d data points for %s", len(paths), message_id[:8])
        return paths

    async def write_raw_data_chunks(
        self,
        message_id: str,
        chunks: list[str],
        source: str,
    ) -> list[str]:
        """Write raw unclassified content chunks to 01-Data.

        These are atomic segments of the original source material, not
        LLM-extracted concepts. Classification happens in 02-Information.

        Returns a list of dikiwi_ids (one per chunk written) so downstream
        stages can link back to the raw data.
        """
        day_dir = self._get_day_dir("01-Data")
        ids: list[str] = []

        # Pre-filter to count only chunks that will actually be written
        valid_chunks: list[tuple[int, str, str]] = []
        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if not chunk:
                continue
            cleaned = re.sub(r"<!--.*?-->", "", chunk).strip()
            if len(cleaned.split()) < 3:
                continue
            # Decode HTML entities so titles and slugs are readable
            cleaned = html.unescape(cleaned)
            valid_chunks.append((i, chunk, cleaned))

        total_written = len(valid_chunks)

        for write_idx, (orig_idx, chunk, cleaned) in enumerate(valid_chunks):
            # Use the same title extraction for filename slug as for the heading
            chunk_title = self._extract_chunk_title(cleaned, orig_idx)
            if chunk_title.startswith("Data Chunk "):
                # Fallback: find the first meaningful line and slugify it
                # Re-use the same heuristics _extract_chunk_title uses
                def _line_ok(line: str) -> bool:
                    text = line.strip()
                    if not text or len(text) < 4:
                        return False
                    words = text.split()
                    if len(words) < 3:
                        return False
                    if all(w.isupper() and len(w) <= 8 for w in words):
                        return False
                    avg = sum(len(w) for w in words) / len(words)
                    if avg < 2.5:
                        return False
                    if text in ("•", "-", "*", "<!-- image -->"):
                        return False
                    if text.startswith("<!--") and text.endswith("-->"):
                        return False
                    return True

                fallback_title = None
                for line in cleaned.splitlines():
                    if _line_ok(line):
                        fallback_title = " ".join(line.split())
                        break
                if fallback_title:
                    slug = _slugify_title(fallback_title, max_length=40).replace("-", "_")
                else:
                    slug = f"chunk-{orig_idx}"
            else:
                # Slugify the extracted title for a meaningful filename
                slug = _slugify_title(chunk_title, max_length=40).replace("-", "_")
            if not slug:
                slug = f"chunk-{orig_idx}"
            # Prefix with message_id to avoid collisions across pipelines
            safe_id = f"{message_id[:8]}_{slug}-{orig_idx}"
            dikiwi_id = f"data-{safe_id}"
            self._id_to_title[dikiwi_id] = slug
            note_path = day_dir / f"{dikiwi_id}-{slug}.md"

            frontmatter = {
                "dikiwi_stage": "data",
                "pipeline_id": message_id,
                "chunk_index": orig_idx,
                "source": source,
                "date_created": datetime.now().astimezone().isoformat(),
                "word_count": len(chunk.split()),
                "status": "unclassified",
                "tags": ["dikiwi", "data", "unclassified"],
            }

            # Decode HTML entities from pdfplumber extraction for readability
            readable_chunk = html.unescape(chunk)
            content_lines = [
                self._format_frontmatter(frontmatter),
                "",
                f"# {chunk_title}",
                "",
                readable_chunk,
                "",
                "---",
                "",
                "## Metadata",
                f"- **Source**: {source}",
                f"- **Chunk**: {write_idx + 1} of {total_written}",
                f"- **Words**: {len(readable_chunk.split())}",
            ]

            note_path.write_text("\n".join(content_lines), encoding="utf-8")
            ids.append(dikiwi_id)

        logger.info("Wrote %d raw data chunks for %s", len(ids), message_id[:8])
        return ids

    async def write_information_nodes(
        self,
        message_id: str,
        nodes: list[Any],
    ) -> list[Path]:
        """Write information nodes to 02-Information."""
        if self.zettelkasten_only:
            return []

        day_dir = self._get_day_dir("02-Information")
        paths = []

        for i, node in enumerate(nodes):
            note_path = day_dir / f"info-{message_id}-{i}.md"

            # Handle both dataclass objects and dicts
            if isinstance(node, dict):
                content = node.get("content", "")
                domain = node.get("domain", "")
                info_type = node.get("info_type", "")
                tags = node.get("tags", [])
            else:
                content = getattr(node, "content", "")
                domain = getattr(node, "domain", "")
                info_type = getattr(node, "info_type", "")
                tags = getattr(node, "tags", [])

            frontmatter = {
                "dikiwi_stage": "information",
                "message_id": message_id,
                "domain": domain,
                "info_type": info_type,
                "date_created": datetime.now().astimezone().isoformat(),
                "tags": ["dikiwi", "information", domain] + tags,
            }

            note_content = f"""{self._format_frontmatter(frontmatter)}

# Information: {domain}

{content}
"""
            note_path.write_text(note_content, encoding="utf-8")
            paths.append(note_path)

        logger.info("Wrote %d information nodes for %s", len(paths), message_id[:8])
        return paths

    async def write_knowledge_relations(
        self,
        message_id: str,
        relations: list[Any],
    ) -> list[Path]:
        """Write knowledge relations to 03-Knowledge."""
        if self.zettelkasten_only:
            return []

        day_dir = self._get_day_dir("03-Knowledge")
        paths = []

        for i, relation in enumerate(relations):
            note_path = day_dir / f"knowledge-{message_id}-{i}.md"

            # Handle both dataclass objects and dicts
            if isinstance(relation, dict):
                source_id = relation.get("source_id", "")
                target_id = relation.get("target_id", "")
                relation_type = relation.get("relation_type", "")
                strength = relation.get("strength", 0.0)
            else:
                source_id = getattr(relation, "source_id", "")
                target_id = getattr(relation, "target_id", "")
                relation_type = getattr(relation, "relation_type", "")
                strength = getattr(relation, "strength", 0.0)

            frontmatter = {
                "dikiwi_stage": "knowledge",
                "message_id": message_id,
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": relation_type,
                "strength": strength,
                "date_created": datetime.now().astimezone().isoformat(),
                "tags": ["dikiwi", "knowledge", relation_type],
            }

            note_content = f"""{self._format_frontmatter(frontmatter)}

# Knowledge Link

**Source:** {source_id}
**Target:** {target_id}
**Relation:** {relation_type}
**Strength:** {strength}
"""
            note_path.write_text(note_content, encoding="utf-8")
            paths.append(note_path)

        logger.info("Wrote %d knowledge relations for %s", len(paths), message_id[:8])
        return paths

    async def write_insights(
        self,
        message_id: str,
        insights: list[Insight_v2],
        source_title: str,
    ) -> list[Path]:
        """Write insights to 04-Insight with rich Dataview metadata."""
        if self.zettelkasten_only:
            return []

        day_dir = self._get_day_dir("04-Insight")
        paths = []

        for i, insight in enumerate(insights):
            note_path = day_dir / f"insight-{message_id}-{i}.md"

            frontmatter = {
                "dikiwi_stage": "insight",
                "insight_id": f"{message_id}-{i}",
                "insight_type": insight.insight_type,
                "confidence": round(insight.confidence, 2),
                "source_message": f"00-Chaos/{message_id}",
                "source_title": source_title,
                "date_created": datetime.now().astimezone().isoformat(),
                "tags": [
                    "dikiwi",
                    "insight",
                    insight.insight_type,
                ],
            }

            # Add emoji based on type
            emoji_map = {
                "theme": "🎯",
                "contradiction": "⚡",
                "opportunity": "💡",
                "gap": "🔗",
                "pattern": "🔍",
                "tension": "↔️",
            }
            emoji = emoji_map.get(insight.insight_type, "📌")

            content_lines = [
                self._format_frontmatter(frontmatter),
                f"",
                f"# {emoji} {insight.insight_type.title()}: {insight.description[:50]}",
                f"",
                f"{insight.description}",
                f"",
                f"---",
                f"",
                f"## Analysis",
                f"- **Confidence**: `{insight.confidence:.0%}`",
                f"- **Type**: #{insight.insight_type}",
                f"- **Source**: [[{source_title}]]",
                f"",
                f"---",
                f"",
                f"## Related Insights",
                f"```dataview",
                f"TABLE insight_type, confidence",
                f'FROM "04-Insight"',
                f"WHERE insight_type = this.insight_type AND confidence > 0.7",
                f"SORT confidence DESC",
                f"LIMIT 10",
                f"```",
            ]

            note_path.write_text("\n".join(content_lines), encoding="utf-8")
            paths.append(note_path)

        logger.info("Wrote %d insights for %s", len(paths), message_id[:8])
        return paths

    async def write_wisdom(
        self,
        message_id: str,
        wisdom_items: list[Any],
    ) -> list[Path]:
        """Write wisdom principles to 05-Wisdom."""
        day_dir = self._get_day_dir("05-Wisdom")
        paths = []

        for i, wisdom in enumerate(wisdom_items):
            note_path = day_dir / f"wisdom-{message_id}-{i}.md"

            # Handle both dataclass objects and dicts
            if isinstance(wisdom, dict):
                principle = wisdom.get('principle', '')
                context = wisdom.get('context', '')
                implications = wisdom.get('implications', [])
            else:
                principle = getattr(wisdom, 'principle', '')
                context = getattr(wisdom, 'context', '')
                implications = getattr(wisdom, 'implications', [])

            frontmatter = {
                "dikiwi_stage": "wisdom",
                "wisdom_id": f"{message_id}-{i}",
                "date_created": datetime.now().astimezone().isoformat(),
                "tags": ["dikiwi", "wisdom", "principle"],
            }

            content_lines = [
                self._format_frontmatter(frontmatter),
                f"",
                f"# 🧠 Principle: {principle[:50] if principle else 'Untitled'}",
                f"",
                f"{principle}",
                f"",
                f"## Context",
                f"{context}",
                f"",
                f"## Implications",
            ]
            for impl in implications:
                content_lines.append(f"- {impl}")
            if not implications:
                content_lines.append("- _No specific implications recorded_")

            content_lines.extend([])

            note_path.write_text("\n".join(content_lines), encoding="utf-8")
            paths.append(note_path)

        logger.info("Wrote %d wisdom items for %s", len(paths), message_id[:8])
        return paths

    async def write_impact(
        self,
        message_id: str,
        impacts: list[Any],
    ) -> list[Path]:
        """Write impact proposals to 06-Impact as tasks."""
        if self.zettelkasten_only:
            return []

        day_dir = self._get_day_dir("06-Impact")
        paths = []

        for i, impact in enumerate(impacts):
            note_path = day_dir / f"impact-{message_id}-{i}.md"

            # Handle both dataclass objects and dicts
            if isinstance(impact, dict):
                proposal = impact.get('proposal', '')
                rationale = impact.get('rationale', '')
                proposal_type = impact.get('proposal_type', 'task')
                priority = impact.get('priority', 'medium')
                expected_outcome = impact.get('expected_outcome', 'TBD')
            else:
                proposal = getattr(impact, 'proposal', '')
                rationale = getattr(impact, 'rationale', '')
                proposal_type = getattr(impact, 'proposal_type', 'task')
                priority = getattr(impact, 'priority', 'medium')
                expected_outcome = getattr(impact, 'expected_outcome', 'TBD')

            frontmatter = {
                "dikiwi_stage": "impact",
                "impact_id": f"{message_id}-{i}",
                "proposal_type": proposal_type,
                "priority": priority,
                "status": "active",
                "date_created": datetime.now().astimezone().isoformat(),
                "tags": ["dikiwi", "impact", "proposal", str(proposal_type)],
            }

            content_lines = [
                self._format_frontmatter(frontmatter),
                f"",
                f"# 🚀 Proposal: {proposal[:50] if proposal else 'Untitled'}",
                f"",
                f"{proposal}",
                f"",
                f"## Rationale",
                f"{rationale}",
                f"",
                f"## Expected Outcome",
                f"{expected_outcome}",
                f"",
                f"---",
                f"",
                f"## Task",
                f"- [ ] {proposal}",
                f"",
            ]

            note_path.write_text("\n".join(content_lines), encoding="utf-8")
            paths.append(note_path)

        logger.info("Wrote %d impact proposals for %s", len(paths), message_id[:8])
        return paths

    async def write_zettel(
        self,
        zettel_id: str,
        title: str,
        content: str,
        tags: list[str],
        links_to: list[str],
        source: str = "",
        source_paths: list[str] | None = None,
        dikiwi_level: str = "wisdom",
    ) -> Path:
        """Write a Zettelkasten permanent note.

        Creates a proper atomic note in the Zettelkasten folder with:
        - YAML frontmatter with metadata
        - Full content (300-500 words)
        - Tags and links sections
        """
        folder = self.LEVEL_TO_FOLDER.get(dikiwi_level, "05-Wisdom")
        date_dir = self._get_day_dir(folder)

        # Sanitize title for filename
        safe_title = _slugify_title(title)
        self._id_to_title[zettel_id] = safe_title
        filename = f"{zettel_id}-{safe_title}.md"
        note_path = date_dir / filename

        # Build frontmatter
        frontmatter = {
            "zettel_id": zettel_id,
            "title": title,
            "aliases": [title],
            "source": source,
            "date_created": datetime.now().astimezone().isoformat(),
            "note_type": "permanent",
            "dikiwi_level": dikiwi_level,
            "word_count": len(content.split()),
        }
        if source_paths:
            frontmatter["source_paths"] = _dedupe_preserve_order(source_paths)
        deduped_tags = _dedupe_preserve_order([dikiwi_level, *tags])
        if deduped_tags:
            frontmatter["tags"] = deduped_tags

        # Build content
        content_lines = [
            self._format_frontmatter(frontmatter),
            f"",
            f"# {title}",
            f"",
            content,
            f"",
        ]

        # Add related section if there are links
        if links_to:
            content_lines.extend([
                f"## Related",
                f"",
            ])
            for link in links_to:
                content_lines.append(f"- [[{link}]]")
            content_lines.append("")

        content_lines.extend([
            f"---",
            f"",
            f"*Source: {source}*",
        ])

        note_path.write_text("\n".join(content_lines), encoding="utf-8")
        self._update_topic_maps(tags)
        logger.info("Wrote Zettelkasten note: %s (%d words)", filename, len(content.split()))

        return note_path

    async def create_message_canvas(
        self,
        message_id: str,
        stage_files: dict[str, list[str]],
    ) -> Path:
        """Create a Canvas visualization for a specific message."""
        canvas_path = self.dikiwi_root / "Canvas" / f"Message-{message_id}.canvas"

        nodes = []
        edges = []
        x_pos = 0

        stage_colors = {
            "data": "2",      # Orange
            "information": "3",  # Yellow
            "knowledge": "4",    # Green
            "insights": "5",     # Blue
            "wisdom": "6",       # Purple
            "impact": "7",       # Pink
        }

        for stage, files in stage_files.items():
            for i, file_path in enumerate(files):
                node_id = f"{stage}-{i}"
                nodes.append({
                    "id": node_id,
                    "type": "file",
                    "file": file_path.replace(".md", ""),
                    "x": x_pos,
                    "y": i * 200,
                    "width": 280,
                    "height": 180,
                    "color": stage_colors.get(stage, "1"),
                })

            # Connect to next stage
            if len(nodes) > len(files) and len(files) > 0:
                edges.append({
                    "fromNode": f"{stage}-0",
                    "toNode": f"{list(stage_files.keys())[list(stage_files.keys()).index(stage) + 1]}-0",
                    "label": "→",
                })

            x_pos += 350

        canvas_data = {"nodes": nodes, "edges": edges}
        canvas_path.write_text(json.dumps(canvas_data, indent=2), encoding="utf-8")

        logger.info("Created canvas: %s", canvas_path)
        return canvas_path

    async def create_insight_dashboard(self) -> Path:
        """Create a comprehensive insight dashboard."""
        dashboard_path = self.dikiwi_root / "04-Insight" / "Insight-Dashboard.md"

        content = """---
tags: [dashboard, dikiwi, insights]
---

# DIKIWI Insight Dashboard

## Overview Stats
```dataviewjs
const insights = dv.pages('"04-Insight"').where(p => p.insight_type);
const wisdom = dv.pages('"05-Wisdom"').where(p => p.dikiwi_stage == "wisdom");
const impact = dv.pages('"06-Impact"').where(p => p.dikiwi_stage == "impact");

const highConfidence = insights.where(p => p.confidence >= 0.8).length;
const medConfidence = insights.where(p => p.confidence >= 0.6 && p.confidence < 0.8).length;
const lowConfidence = insights.where(p => p.confidence < 0.6).length;

dv.table(["Metric", "Count"], [
  ["📝 Total Insights", insights.length],
  ["✨ High Confidence (≥0.8)", highConfidence],
  ["📊 Medium Confidence (0.6-0.8)", medConfidence],
  ["⚠️ Low Confidence (<0.6)", lowConfidence],
  ["🧠 Wisdom Principles", wisdom.length],
  ["🚀 Active Proposals", impact.where(p => p.status == "active").length],
]);
```

## Insights by Type
```dataviewjs
const byType = dv.pages('"04-Insight"')
  .groupBy(p => p.insight_type)
  .sort(g => g.rows.length, 'desc');

dv.table(["Type", "Count", "Avg Confidence"],
  byType.map(g => [
    g.key || "uncategorized",
    g.rows.length,
    (g.rows.reduce((sum, r) => sum + (r.confidence || 0), 0) / g.rows.length).toFixed(2)
  ])
);
```

## Recent High-Confidence Insights
```dataview
TABLE insight_type, confidence, source_title
FROM "04-Insight"
WHERE confidence >= 0.8
SORT date_created DESC
LIMIT 10
```

## Top Opportunities
```dataview
TABLE confidence, source_title
FROM "04-Insight"
WHERE insight_type = "opportunity"
SORT confidence DESC
LIMIT 5
```

## Active Proposals
```dataview
TABLE proposal_type, priority
FROM "06-Impact"
WHERE status = "active"
SORT priority DESC
```

## Tasks
```tasks
not done
path includes 06-Impact
```

---

*Generated by DIKIWI Obsidian Integration*
"""

        dashboard_path.write_text(content, encoding="utf-8")
        logger.info("Created dashboard: %s", dashboard_path)
        return dashboard_path

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the DIKIWI vault."""
        stats = {
            "stages": {},
            "total_notes": 0,
            "canvas_files": 0,
        }

        for stage_num, stage_name in self.STAGE_NAMES.items():
            stage_dir = self.dikiwi_root / stage_name
            if stage_dir.exists():
                md_files = list(stage_dir.rglob("*.md"))
                stats["stages"][stage_name] = len(md_files)
                stats["total_notes"] += len(md_files)

        canvas_dir = self.dikiwi_root / "Canvas"
        if canvas_dir.exists():
            canvas_files = list(canvas_dir.glob("*.canvas"))
            stats["canvas_files"] = len(canvas_files)

        return stats
