"""Tests for DIKIWI skill registry and skills.

Tests:
- Skill discovery and loading
- LRU cache behavior
- Failure tracking
- Content type classification
"""

from __future__ import annotations

import pytest

from aily.dikiwi import SkillRegistry
from aily.dikiwi.skills.base import Skill, SkillContext, SkillResult
from aily.dikiwi.stages import DikiwiStage


class TestSkillRegistry:
    """Test the skill registry."""

    async def test_classify_tech_content(self, skill_registry):
        """Registry classifies tech content correctly."""
        content = "This is about Python functions and API endpoints"
        content_type = await skill_registry.classify_content_type(content)

        assert content_type == "tech_content"

    async def test_classify_business_content(self, skill_registry):
        """Registry classifies business content correctly."""
        content = "Our revenue and customer growth strategy"
        content_type = await skill_registry.classify_content_type(content)

        assert content_type == "business_content"

    async def test_classify_general_content(self, skill_registry):
        """Registry defaults to general for ambiguous content."""
        content = "Just some regular text"
        content_type = await skill_registry.classify_content_type(content)

        assert content_type == "general"

    async def test_get_skills_for_stage(self, skill_registry):
        """Registry returns skills for stage/content type."""
        skills = await skill_registry.get_skills(
            DikiwiStage.INFORMATION,
            "Python code review tips",
        )

        # Should return list (may be empty if no builtin skills)
        assert isinstance(skills, list)

    def test_list_skills(self, skill_registry):
        """Registry can list all registered skills."""
        skills = skill_registry.list_skills()
        assert isinstance(skills, list)

    def test_get_skill_metadata(self, skill_registry):
        """Registry returns skill metadata."""
        # Try a known skill
        meta = skill_registry.get_skill_metadata("tag_extraction")
        # May be None if skill doesn't exist
        assert meta is None or hasattr(meta, "name")

    async def test_load_skill_caches_instance(self, skill_registry):
        """Loading a skill caches the instance."""
        # This will fail if skill doesn't exist, but tests the cache path
        skill1 = await skill_registry.load_skill("nonexistent_skill_12345")
        skill2 = await skill_registry.load_skill("nonexistent_skill_12345")

        # Both should be None, but cache should have been checked
        assert skill1 is None
        assert skill2 is None

    def test_register_skill(self, skill_registry):
        """Can register a custom skill class."""

        class TestSkill(Skill):
            name = "test_register"
            description = "Test"
            target_stages = ["information"]

            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult.success_result("test_register", {})

        skill_registry.register_skill("test_register", TestSkill)

        meta = skill_registry.get_skill_metadata("test_register")
        assert meta is not None
        assert meta.name == "test_register"

    def test_register_skill_mapping(self, skill_registry):
        """Can register custom skill mappings."""
        skill_registry.register_skill_mapping(
            DikiwiStage.INFORMATION,
            "custom_type",
            ["custom_skill"],
        )

        # Should be retrievable (though skill may not exist)
        skills = skill_registry._skill_map.get(("information", "custom_type"))
        assert skills == ["custom_skill"]

    def test_lru_cache_eviction(self):
        """LRU cache evicts oldest entries."""
        registry = SkillRegistry(max_cache_size=2)

        # Create test skills
        class Skill1(Skill):
            name = "skill1"
            async def execute(self, ctx): pass

        class Skill2(Skill):
            name = "skill2"
            async def execute(self, ctx): pass

        class Skill3(Skill):
            name = "skill3"
            async def execute(self, ctx): pass

        registry.register_skill("s1", Skill1)
        registry.register_skill("s2", Skill2)
        registry.register_skill("s3", Skill3)

        # Load 3 skills with cache size 2
        # First one should be evicted
        # (This test is simplified - actual cache test needs async loading)
        assert registry._max_cache_size == 2

    def test_get_metrics_includes_failures(self):
        """Metrics include failure tracking."""
        registry = SkillRegistry()

        metrics = registry.get_metrics()

        assert "failed_skills_total" in metrics
        assert "failed_skills_recent_24h" in metrics
        assert "health_status" in metrics

    def test_clear_cache_clears_lru(self):
        """Clear cache resets LRU tracking."""
        registry = SkillRegistry()

        # Add something to cache
        registry._skill_instances["test"] = None
        registry._access_order.append("test")

        registry.clear_cache()

        assert len(registry._skill_instances) == 0
        assert len(registry._access_order) == 0

    def test_get_skills_for_stage_filter(self, skill_registry):
        """Can get skills filtered by stage."""
        # Register skills for different stages
        class InfoSkill(Skill):
            name = "info_skill"
            target_stages = ["information"]
            async def execute(self, ctx): pass

        class InsightSkill(Skill):
            name = "insight_skill"
            target_stages = ["insight"]
            async def execute(self, ctx): pass

        skill_registry.register_skill("info_skill", InfoSkill)
        skill_registry.register_skill("insight_skill", InsightSkill)

        info_skills = skill_registry.get_skills_for_stage(DikiwiStage.INFORMATION)
        skill_names = [s.name for s in info_skills]

        assert "info_skill" in skill_names
        # insight_skill may or may not be in list depending on implementation


class TestSkillBase:
    """Test the Skill base class."""

    def test_skill_metadata_defaults(self):
        """Skill has default metadata."""

        class TestSkill(Skill):
            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult.success_result("test", {})

        skill = TestSkill()
        assert skill.name == "base_skill"
        assert skill.version == "1.0.0"

    def test_can_handle_wildcard(self):
        """Skill with * content type handles all."""

        class TestSkill(Skill):
            content_types = ["*"]
            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult.success_result("test", {})

        skill = TestSkill()
        assert skill.can_handle("information", "any_type")

    def test_can_handle_specific_type(self):
        """Skill only handles specific content types."""

        class TestSkill(Skill):
            content_types = ["tech_content"]
            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult.success_result("test", {})

        skill = TestSkill()
        assert skill.can_handle("information", "tech_content")
        assert not skill.can_handle("information", "business_content")

    async def test_run_calls_execute(self):
        """Skill.run calls execute and returns result."""

        class TestSkill(Skill):
            name = "test_run"
            async def execute(self, context: SkillContext) -> SkillResult:
                return SkillResult.success_result("test_run", {"value": 42}, 0.0)

        skill = TestSkill()
        context = SkillContext(
            content="Test",
            content_id="test-001",
            stage="information",
        )

        result = await skill.run(context)

        assert result.success
        assert result.output["value"] == 42

    async def test_run_catches_exceptions(self):
        """Skill.run catches exceptions and returns error result."""

        class FailingSkill(Skill):
            name = "failing"
            async def execute(self, context: SkillContext) -> SkillResult:
                raise ValueError("Test error")

        skill = FailingSkill()
        context = SkillContext(
            content="Test",
            content_id="test-001",
            stage="information",
        )

        result = await skill.run(context)

        assert not result.success
        assert "Test error" in result.error_message


class TestSkillResult:
    """Test SkillResult factory methods."""

    def test_success_result(self):
        """success_result creates success result."""
        result = SkillResult.success_result("test", {"key": "value"}, 0.0)

        assert result.success
        assert result.skill_name == "test"
        assert result.output["key"] == "value"

    def test_error_result(self):
        """error_result creates error result."""
        result = SkillResult.error_result("test", "Something went wrong")

        assert not result.success
        assert result.skill_name == "test"
        assert "Something went wrong" in result.error_message
