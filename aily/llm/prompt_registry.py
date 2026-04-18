from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PromptSpec:
    """Structured prompt spec used to keep stage prompts aligned."""

    stage: str
    role: str
    objective: str
    output_contract: str
    guidelines: tuple[str, ...]
    context_sections: tuple[tuple[str, str], ...]
    extra_notes: str = ""


class DikiwiPromptRegistry:
    """Central prompt registry for the DIKIWI pipeline.

    The goal is to keep every stage aligned to the same mission:
    transform raw inputs into durable, linkable Zettelkasten knowledge.
    """

    SHARED_MISSION = (
        "You are DIKIWI, Aily's information processing center. "
        "Your job is to turn messy input into durable Zettelkasten knowledge. "
        "Every stage must stay aligned to the same mission: preserve meaning, "
        "identify concepts, connect ideas, and create reusable notes instead of shallow summaries."
    )

    SHARED_PRINCIPLES = (
        "Maintain continuity with the prior stages and shared memory.",
        "Prefer conceptual clarity over extraction noise.",
        "Write in service of long-term knowledge, not one-off task completion.",
        "Optimize for atomic, linkable, reusable notes.",
        "A permanent note is not a summary of a source; it preserves one useful idea from the source in durable form.",
        "Long or technical sources should usually yield multiple notes when they contain multiple distinct ideas.",
        "Be explicit when uncertainty is high instead of hallucinating structure.",
        "Return valid JSON only.",
    )

    DATA_EXTRACTION_CONTRACT = """Respond with JSON:
{
  "title": "Document or content title if identifiable, otherwise empty string",
  "data_points": [
    {
      "concept": "Short name for this concept (3-8 words)",
      "content": "2-5 sentence explanation with specific details: what it is, why it matters, and how it works. Must stand alone without reading the source. Avoid vague abstractions.",
      "context": "Section or topic area this comes from",
      "confidence": 0.0-1.0,
      "type": "mechanism|finding|method|principle|definition|tradeoff|constraint|example|fact|claim"
    }
  ],
  "summary": "One paragraph summary of the entire content section",
  "quality_assessment": "high|medium|low"
}
Prefer depth over breadth."""

    FALLBACK_EXTRACTION_CONTRACT = """Respond with JSON:
{
  "summary": "A concise summary of the key information",
  "key_takeaway": "The single most important point",
  "confidence": 0.0-1.0
}"""

    CLASSIFICATION_CONTRACT = """Respond with JSON:
{
  "tags": ["tag1", "tag2", "tag3"],
  "info_type": "fact|claim|evidence|opinion|definition|hypothesis|question",
  "domain": "technology|business|science|philosophy|arts|general|engineering|ai|semiconductor|eda",
  "confidence": 0.0-1.0,
  "reasoning": "Why these classifications were chosen"
}"""

    RELATION_CONTRACT = """Respond with JSON:
{
  "relation_type": "supports|contradicts|relates_to|part_of|leads_to|example_of|none",
  "strength": 0.0-1.0,
  "reasoning": "Explanation of the relationship",
  "bidirectional": true|false
}"""

    INSIGHT_CONTRACT = """Respond with JSON:
{
  "insights": [
    {
      "type": "theme|contradiction|opportunity|gap|pattern|tension|path",
      "description": "Clear description of the short path formed by linked information. Show how 2-4 connected nodes reveal something neither node shows alone.",
      "confidence": 0.0-1.0,
      "related_node_indices": [0, 1, 2],
      "significance": "Why traversing this small path matters"
    }
  ],
  "synthesis": "Overall summary of what this knowledge network represents as a set of short traversable paths",
  "knowledge_gaps": ["Areas where more information would create longer paths"]
}
"""

    WISDOM_CONTRACT = """Respond with JSON:
{
  "zettels": [
    {
      "title": "Full sentence describing the core idea or long-path principle",
      "content": "Complete markdown content (150-400 words) in full paragraphs. Synthesize several paths and long paths into a more complex graph structure. Show how multiple insights interlock into durable principles.",
      "tags": ["domain", "concept", "application"],
      "links_to": ["Related concept 1", "Related concept 2", "Contrasting idea", "Long-path principle"],
      "confidence": 0.0-1.0,
      "source_evidence": [
        "Specific information fragment from the source that supports this note"
      ]
    }
  ],
  "note_strategy": "Explain how you split the source into separate permanent notes and how they form interlocking paths"
}
"""

    IMPACT_CONTRACT = """Respond with JSON:
{
  "impacts": [
    {
      "type": "innovation|opportunity|action|research|exploration|breakthrough",
      "description": "High-leverage actionable proposal — the center that could explode as the next big thing",
      "priority": "high|medium|low",
      "rationale": "Why this follows from the wisdom and why it has explosive potential",
      "effort_estimate": "small|medium|large",
      "potential_value": "Brief description of expected value and explosive upside"
    }
  ]
}
"""

    RESIDUAL_SYNTHESIS_CONTRACT = """Respond with JSON:
{
  "report_title": "Title for the formal summary report",
  "summary": "3-5 paragraph executive summary of what DIKIWI discovered",
  "key_findings": [
    "First key finding",
    "Second key finding"
  ],
  "reactor_synthesis": "Assessment of how Reactor framework proposals complement or conflict with vault insights",
  "proposals": [
    {
      "title": "Proposal title",
      "description": "Detailed proposal description (2-4 sentences)",
      "domain": "technology|business|science|general",
      "priority": "high|medium|low",
      "rationale": "Why this proposal is supported by the vault contents and/or Reactor frameworks",
      "source_evidence": ["Specific note, insight, or framework that supports this"],
      "framework_contribution": "Which Reactor framework(s) contributed, if any"
    }
  ],
  "recommended_next_steps": [
    "Specific action recommendation"
  ]
}"""

    @classmethod
    def _build_messages(cls, spec: PromptSpec) -> list[dict[str, str]]:
        system_lines = [
            cls.SHARED_MISSION,
            "",
            f"Current stage: {spec.stage}",
            f"Current role: {spec.role}",
            f"Objective: {spec.objective}",
            "",
            "Shared operating principles:",
        ]
        system_lines.extend(f"- {line}" for line in cls.SHARED_PRINCIPLES)
        system_lines.extend(f"- {line}" for line in spec.guidelines)
        if spec.extra_notes:
            system_lines.extend(["", spec.extra_notes])

        user_lines = [spec.output_contract]
        for title, body in spec.context_sections:
            user_lines.extend(["", f"## {title}", body])

        return [
            {"role": "system", "content": "\n".join(system_lines)},
            {"role": "user", "content": "\n".join(user_lines)},
        ]

    @staticmethod
    def render_memory(memory: object | None, limit: int = 1800) -> str:
        """Render a compact shared-memory section if available."""
        if memory is None or not hasattr(memory, "messages"):
            return ""

        messages = getattr(memory, "messages", [])
        if len(messages) <= 1:
            return ""

        if hasattr(memory, "to_prompt_context"):
            context = memory.to_prompt_context()
        else:
            context = "\n".join(
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:400]}"
                for msg in messages
                if isinstance(msg, dict)
            )

        context = context[-limit:].strip()
        if not context:
            return ""

        return f"Use this shared pipeline memory to stay consistent with earlier stages:\n{context}"

    CLASSIFICATION_BATCH_CONTRACT = """Respond with JSON:
{
  "classifications": [
    {
      "index": 0,
      "tags": ["tag1", "tag2", "tag3"],
      "info_type": "fact|claim|evidence|opinion|definition|hypothesis|question",
      "domain": "technology|business|science|philosophy|arts|general|engineering|ai|semiconductor|eda",
      "confidence": 0.0-1.0
    }
  ]
}
One entry per input item matching its index. Maximum 5 tags per item. Use a single domain value, not pipe-separated."""

    @classmethod
    def data_extraction(
        cls,
        *,
        source: str,
        content: str,
        memory_context: str = "",
        existing_concepts: list[str] | None = None,
    ) -> list[dict[str, str]]:
        existing_note = ""
        if existing_concepts:
            existing_note = (
                "Already extracted concepts (avoid duplication): "
                + ", ".join(existing_concepts[:20])
            )
        spec = PromptSpec(
            stage="DATA",
            role="Data Distiller",
            objective="Extract meaningful concept-level data points from raw material. Each point must be a 2-5 sentence standalone explanation of one idea.",
            output_contract=cls.DATA_EXTRACTION_CONTRACT,
            guidelines=(
                "Extract one concept per data point — not a sentence fragment.",
                "Write content that stands alone without reading the source document.",
                "Include what, why, and how for each concept.",
                "Identify the document title if present.",
                "Skip concepts already listed in 'existing_concepts' to avoid duplication.",
                "Prefer depth over breadth: fewer rich concepts beat many thin extractions.",
                "Return at most 8 data points. If there are more ideas, keep only the most significant.",
                "NEVER use generic abstraction filler: 'strategic pathways', 'involves', 'advantages for specialized hardware', 'plays a crucial role', 'is important because', 'has significant implications'.",
                "Every data point must contain a SPECIFIC claim: a named technology, a numbered threshold, a causal mechanism, or a concrete tradeoff. If the source lacks specifics, return an empty data_points array with quality_assessment 'low'.",
                "If the source is clearly a landing page, share-page wrapper, or table of contents with no substantive body text, return data_points: [] and quality_assessment: 'low'. Do NOT hallucinate concepts from titles alone.",
                "State ideas in your own words, but anchor every claim to a specific detail from the source.",
            ),
            context_sections=(
                ("Source", source),
                ("Content", f"---\n{content}\n---"),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
                *((("Existing Concepts", existing_note),) if existing_note else ()),
            ),
            extra_notes=existing_note,
        )
        return cls._build_messages(spec)

    @classmethod
    def classification_batch(
        cls,
        *,
        data_points: list,
        source: str,
        memory_context: str = "",
    ) -> list[dict[str, str]]:
        items_desc = "\n".join(
            f"{i}. [{getattr(dp, 'concept', '') or getattr(dp, 'content', '')[:40]}] "
            f"{getattr(dp, 'content', '')[:200]}"
            for i, dp in enumerate(data_points[:30])
        )
        spec = PromptSpec(
            stage="INFORMATION",
            role="Semantic Classifier",
            objective="Classify all data points in one pass into conceptual entries for the knowledge graph and Zettelkasten.",
            output_contract=cls.CLASSIFICATION_BATCH_CONTRACT,
            guidelines=(
                "Use conceptual tags that a human would search or link by.",
                "Prefer expert terminology over generic buckets.",
                "For domain, use a single value — no pipe-separated multi-values.",
                "Choose tags that increase future cross-linking value.",
            ),
            context_sections=(
                ("Source", source),
                ("Numbered Items", items_desc),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
        )
        return cls._build_messages(spec)

    @classmethod
    def fallback_extraction(cls, *, source: str, content_preview: str) -> list[dict[str, str]]:
        spec = PromptSpec(
            stage="DATA",
            role="Recovery Summarizer",
            objective="Recover a useful atomic point when full extraction fails.",
            output_contract=cls.FALLBACK_EXTRACTION_CONTRACT,
            guidelines=(
                "Produce a meaningful point rather than an apology.",
                "Preserve the most reusable idea.",
            ),
            context_sections=(
                ("Source", source),
                ("Content Preview", content_preview),
            ),
        )
        return cls._build_messages(spec)

    @classmethod
    def classification(
        cls,
        *,
        content: str,
        context: str,
        source: str,
        memory_context: str = "",
    ) -> list[dict[str, str]]:
        spec = PromptSpec(
            stage="INFORMATION",
            role="Semantic Classifier",
            objective="Classify a data point into reusable conceptual entry points for the knowledge graph and Zettelkasten.",
            output_contract=cls.CLASSIFICATION_CONTRACT,
            guidelines=(
                "Use conceptual tags that a human would search or link by.",
                "Prefer expert terminology over generic buckets.",
                "Choose tags that increase future cross-linking value.",
            ),
            context_sections=(
                ("Content", content),
                ("Context", context or "No extra context."),
                ("Source", source),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
        )
        return cls._build_messages(spec)

    @classmethod
    def relation(
        cls,
        *,
        node_a: str,
        node_a_tags: Iterable[str],
        node_a_domain: str,
        node_b: str,
        node_b_tags: Iterable[str],
        node_b_domain: str,
        memory_context: str = "",
    ) -> list[dict[str, str]]:
        spec = PromptSpec(
            stage="KNOWLEDGE",
            role="Relationship Cartographer",
            objective="Identify whether two classified ideas have a meaningful conceptual relationship worth preserving.",
            output_contract=cls.RELATION_CONTRACT,
            guidelines=(
                "Only create links that would matter later in a knowledge graph.",
                "Use 'none' when the connection is weak or superficial.",
            ),
            context_sections=(
                ("Item A", f"[{node_a_domain}] {node_a}\nTags: {list(node_a_tags)}"),
                ("Item B", f"[{node_b_domain}] {node_b}\nTags: {list(node_b_tags)}"),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
        )
        return cls._build_messages(spec)

    RELATION_BATCH_CONTRACT = """Respond with JSON:
{
  "links": [
    {
      "node_a_index": 0,
      "node_b_index": 2,
      "relation_type": "supports|contradicts|relates_to|part_of|leads_to|example_of",
      "strength": 0.5-1.0,
      "reasoning": "One-line explanation"
    }
  ]
}
Only include links with strength > 0.5. Omit weak or generic connections. Maximum 15 links."""

    @classmethod
    def relation_batch(
        cls,
        *,
        nodes: list,
        memory_context: str = "",
    ) -> list[dict[str, str]]:
        nodes_desc = "\n".join(
            f"{i}. [{getattr(n, 'domain', 'general')}] {getattr(n, 'content', '')[:200]}"
            f"\n   Tags: {getattr(n, 'tags', [])}"
            for i, n in enumerate(nodes[:20])
        )
        spec = PromptSpec(
            stage="KNOWLEDGE",
            role="Relationship Cartographer",
            objective=(
                "Map the most meaningful conceptual relationships across all nodes in one pass. "
                "Focus on links that would enrich a Zettelkasten knowledge graph."
            ),
            output_contract=cls.RELATION_BATCH_CONTRACT,
            guidelines=(
                "Only create links that would matter later in a knowledge graph.",
                "Prefer specific relation types (leads_to, contradicts) over generic (relates_to).",
                "Skip trivial or superficial connections.",
                "Return at most 15 high-quality links.",
            ),
            context_sections=(
                ("Numbered Information Nodes", nodes_desc),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
        )
        return cls._build_messages(spec)

    @classmethod
    def insight(
        cls,
        *,
        nodes_desc: str,
        links_desc: str,
        memory_context: str = "",
    ) -> list[dict[str, str]]:
        spec = PromptSpec(
            stage="INSIGHT",
            role="Path Synthesizer",
            objective="Discover short paths formed by linked information. Traverse 2-4 connected nodes to find what none of them reveal alone.",
            output_contract=cls.INSIGHT_CONTRACT,
            guidelines=(
                "An insight is a traversable short path across linked information, not a restatement of a single node.",
                "Show how connected nodes produce emergent understanding.",
                "Prefer insights that would justify a permanent note.",
                "Use contradictions and tensions to deepen the slip-box.",
            ),
            context_sections=(
                ("Information Nodes", nodes_desc or "No nodes available."),
                ("Relationships", links_desc or "No explicit relationships available."),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
        )
        return cls._build_messages(spec)

    @classmethod
    def wisdom(
        cls,
        *,
        insights_desc: str,
        info_samples: str,
        memory_context: str = "",
    ) -> list[dict[str, str]]:
        spec = PromptSpec(
            stage="WISDOM",
            role="Zettelkasten Author",
            objective="Synthesize several paths and long paths into a more complex graph structure. Turn source-backed information and short-path insights into durable, interlocking permanent notes.",
            output_contract=cls.WISDOM_CONTRACT,
            guidelines=(
                "Do not produce a source summary masquerading as a note.",
                "Each note should synthesize multiple short paths into a longer, more complex principle.",
                "Split long sources into multiple notes when they contain multiple mechanisms, claims, examples, workflows, constraints, tradeoffs, or definitions.",
                "Write in your own words, not copied fragments.",
                "Make each note timeless, standalone, and link-worthy.",
                "Anchor each note in the source material and preserve its useful informational content.",
                "Prefer several atomic notes over one blended synthesis note.",
                "Include examples, scope, and connections to broader principles when they strengthen the note.",
                "Wisdom is where short paths interlock into a dense, reusable graph structure.",
            ),
            context_sections=(
                ("Insights", insights_desc or "No insights available. Return an empty zettels array."),
                ("Knowledge Base", info_samples or "No information samples available."),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
            extra_notes=(
                "If multiple roles are helpful, internally act as a knowledge editor, "
                "a concept clarifier, and a slip-box librarian before producing the final notes. "
                "Your job is to extract durable ideas from the source, not to compress the source into one overview."
            ),
        )
        return cls._build_messages(spec)

    @classmethod
    def impact(
        cls,
        *,
        zettels_desc: str,
        memory_context: str = "",
    ) -> list[dict[str, str]]:
        spec = PromptSpec(
            stage="IMPACT",
            role="Breakthrough Strategist",
            objective="Identify the center that will explode as the next big thing. Convert the dense graph of wisdom into high-leverage, breakthrough actions.",
            output_contract=cls.IMPACT_CONTRACT,
            guidelines=(
                "Base actions on the permanent notes, not on raw input.",
                "Look for the single highest-leverage point where action could create explosive, compounding effects.",
                "Prefer proposals that feel like the center of a growing force, not incremental improvements.",
                "An impact is not just an action — it is the ignition point for what comes next.",
            ),
            context_sections=(
                ("Zettelkasten Principles", zettels_desc or "No zettels available."),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
        )
        return cls._build_messages(spec)

    @classmethod
    def residual_synthesis(
        cls,
        *,
        vault_excerpts: str,
        graph_nodes: str,
        reactor_proposals: str,
        memory_context: str = "",
    ) -> list[dict[str, str]]:
        spec = PromptSpec(
            stage="RESIDUAL",
            role="Vault Scholar (残差)",
            objective=(
                "Analyze the DIKIWI vault outputs, knowledge graph, and Reactor framework proposals "
                "to draft a formal summary report and concrete proposals for innovation and business evaluation."
            ),
            output_contract=cls.RESIDUAL_SYNTHESIS_CONTRACT,
            guidelines=(
                "Synthesize patterns across vault notes, graph nodes, and Reactor proposals — not just restate them.",
                "Proposals must be grounded in specific evidence from the vault, graph, or Reactor frameworks.",
                "When Reactor frameworks and vault insights conflict, resolve the tension explicitly.",
                "Write as a formal analyst drafting paperwork for the Innovation and Entrepreneur minds.",
                "Prioritize proposals with clear domains, priorities, and rationale.",
                "Return valid JSON only.",
            ),
            context_sections=(
                ("Vault Excerpts", vault_excerpts or "No vault excerpts available."),
                ("Graph Nodes", graph_nodes or "No graph nodes available."),
                ("Reactor Framework Proposals", reactor_proposals or "No Reactor proposals available."),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
        )
        return cls._build_messages(spec)

    @classmethod
    def review(
        cls,
        *,
        stage: str,
        reviewer_role: str,
        objective: str,
        output_contract: str,
        draft_json: str,
        memory_context: str = "",
        review_focus: Iterable[str] = (),
        context_sections: tuple[tuple[str, str], ...] = (),
    ) -> list[dict[str, str]]:
        review_lines = [
            "Review the draft from the previous specialist agent.",
            "Repair weak structure, missing atomicity, and schema mismatches.",
            "Return a corrected final JSON payload, not commentary.",
        ]
        review_lines.extend(f"- {line}" for line in review_focus)

        spec = PromptSpec(
            stage=stage,
            role=reviewer_role,
            objective=objective,
            output_contract=output_contract,
            guidelines=tuple(review_lines),
            context_sections=(
                *context_sections,
                ("Draft JSON", draft_json),
                ("Shared Memory", memory_context or "No earlier stage memory available."),
            ),
        )
        return cls._build_messages(spec)
