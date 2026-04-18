"""LLM-based tagging for semantic content understanding."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from aily.llm.kimi_client import KimiClient

if TYPE_CHECKING:
    from aily.chaos.config import ChaosConfig
    from aily.chaos.types import ExtractedContentMultimodal
    from aily.llm.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class LLMBasedTagger:
    """Generate tags using LLM semantic understanding."""

    def __init__(self, config: "ChaosConfig") -> None:
        self.config = config
        self._client: "LLMRouter | None" = None

    async def tag(self, content: "ExtractedContentMultimodal") -> list[str]:
        """Generate tags using LLM analysis.

        Args:
            content: Extracted content to analyze

        Returns:
            List of semantic tags
        """
        # Build prompt
        prompt = self._build_prompt(content)

        # Call LLM
        try:
            response = await self._call_llm(prompt)
            tags = self._parse_response(response)
            return tags
        except Exception as e:
            logger.warning("LLM tagging failed: %s", e)
            return []

    def _build_prompt(self, content: "ExtractedContentMultimodal") -> str:
        """Build tagging prompt for LLM."""
        # Truncate text if too long
        text = content.text
        max_chars = 4000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"

        prompt = f"""Analyze the following content and generate relevant tags.

Content Title: {content.title or "Unknown"}
Content Type: {content.source_type}

Content Preview:
{text[:2000]}

Generate tags in the following categories:
1. DOMAIN (1-3 tags): Technical domain - e.g., "eda", "ai", "semiconductor", "verification"
2. CONCEPTS (3-5 tags): Key concepts discussed - e.g., "quantization", "mcp", "signoff"
3. ENTITIES (0-3 tags): Named technologies, companies, tools - e.g., "openai", "innovus", "gpt-4"
4. TYPE (1-2 tags): Content type - e.g., "tutorial", "analysis", "reference", "discussion"

Respond with a JSON array of tags only:
["tag1", "tag2", "tag3", ...]
"""
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM for tag generation using the Kimi Open Platform."""
        import os
        import aiohttp

        api_key = (
            os.getenv("KIMI_API_KEY")
            or os.getenv("MOONSHOT_API_KEY")
            or os.getenv("LLM_API_KEY", "")
        )
        if not api_key:
            raise ValueError("No API key found")

        url = KimiClient.CHAT_COMPLETIONS_URL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "kimi-k2.5",
            "messages": [
                {"role": "system", "content": "You are a content tagging assistant. Generate relevant, concise tags for knowledge management."},
                {"role": "user", "content": prompt},
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response.raise_for_status()
                result = await response.json()
                return result["choices"][0]["message"]["content"]

    def _parse_response(self, response: str) -> list[str]:
        """Parse LLM response into tags."""
        try:
            # Try to parse as JSON
            tags = json.loads(response)
            if isinstance(tags, list):
                return [str(tag).strip().lower() for tag in tags if tag]
            elif isinstance(tags, dict) and "tags" in tags:
                return [str(tag).strip().lower() for tag in tags["tags"] if tag]
        except json.JSONDecodeError:
            pass

        # Fallback: extract tags from text
        tags = []
        for line in response.split("\n"):
            line = line.strip()
            # Remove common prefixes
            for prefix in ["-", "*", "•", "tag:", "tags:"]:
                if line.lower().startswith(prefix):
                    line = line[len(prefix):].strip()
            # Clean up
            line = line.strip("'\"[]")
            if line and len(line) > 1:
                tags.append(line.lower())

        return tags
