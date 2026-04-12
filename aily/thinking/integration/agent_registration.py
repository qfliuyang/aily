"""Agent registration for thinking system.

Registers 4 agents with AgentRegistry:
- triz_analyzer: TRIZ framework analysis
- mckinsey_analyzer: McKinsey framework analysis
- gstack_analyzer: GStack framework analysis
- thinking_orchestrator: Full multi-framework orchestration
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aily.agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


async def register_thinking_agents(registry: AgentRegistry) -> None:
    """Register all thinking system agents with the registry.

    Args:
        registry: The AgentRegistry to register with.
    """
    # TRIZ Analyzer Agent
    registry.register(
        name="triz_analyzer",
        agent_fn=_triz_agent_handler,
        description="""
        TRIZ (Theory of Inventive Problem Solving) analyzer.

        Best for: Technical problems, identifying contradictions, finding inventive solutions.

        Capabilities:
        - Detect technical, physical, and administrative contradictions
        - Recommend applicable TRIZ principles (1-40)
        - Analyze evolution trends and S-curve position
        - Define Ideal Final Result (IFR)

        Use when: The problem involves trade-offs, technical constraints, or needs breakthrough thinking.
        """.strip(),
    )
    logger.info("Registered agent: triz_analyzer")

    # McKinsey Analyzer Agent
    registry.register(
        name="mckinsey_analyzer",
        description="""
        McKinsey-style strategic business analyzer.

        Best for: Business strategy, organizational problems, structured analysis.

        Capabilities:
        - Build MECE (Mutually Exclusive, Collectively Exhaustive) structures
        - Generate hypothesis trees for problem solving
        - Apply business frameworks (7S, 3C, Porter 5 Forces)
        - Prioritize issues by impact/effort

        Use when: The problem involves business strategy, market analysis, or organizational challenges.
        """.strip(),
        agent_fn=_mckinsey_agent_handler,
    )
    logger.info("Registered agent: mckinsey_analyzer")

    # GStack Analyzer Agent
    registry.register(
        name="gstack_analyzer",
        description="""
        GStack startup and product strategy analyzer.

        Best for: Startups, product strategy, growth analysis, shipping discipline.

        Capabilities:
        - Analyze product-market fit (PMF score 0-100)
        - Assess shipping velocity and discipline
        - Identify growth loops (viral, paid, UGC, SEO)
        - Evaluate AARRR metrics

        Use when: The problem involves product development, startup strategy, or growth challenges.
        """.strip(),
        agent_fn=_gstack_agent_handler,
    )
    logger.info("Registered agent: gstack_analyzer")

    # Thinking Orchestrator Agent
    registry.register(
        name="thinking_orchestrator",
        description="""
        ARMY OF TOP MINDS thinking orchestrator.

        Best for: Complex problems needing multi-perspective analysis.

        Capabilities:
        - Run TRIZ, McKinsey, and GStack analyzers in parallel
        - Synthesize cross-framework insights
        - Resolve conflicts between frameworks
        - Generate actionable recommendations
        - Output to Obsidian and Feishu

        Use when: You want the most comprehensive analysis combining multiple expert perspectives.
        """.strip(),
        agent_fn=_orchestrator_agent_handler,
    )
    logger.info("Registered agent: thinking_orchestrator")


async def _triz_agent_handler(context: dict[str, Any], text: str) -> str:
    """Handle TRIZ analyzer agent requests.

    Args:
        context: Agent context with dependencies.
        text: Content to analyze.

    Returns:
        TRIZ analysis results as formatted text.
    """
    from aily.thinking.frameworks.triz import TrizAnalyzer
    from aily.thinking.models import KnowledgePayload

    llm_client = context.get("llm_client")
    if not llm_client:
        return "Error: LLM client not available in context"

    analyzer = TrizAnalyzer(llm_client)
    payload = KnowledgePayload(content=text)

    try:
        result = await analyzer.analyze(payload)
        return _format_framework_result(result, "TRIZ")
    except Exception as e:
        return f"TRIZ analysis failed: {e}"


async def _mckinsey_agent_handler(context: dict[str, Any], text: str) -> str:
    """Handle McKinsey analyzer agent requests.

    Args:
        context: Agent context with dependencies.
        text: Content to analyze.

    Returns:
        McKinsey analysis results as formatted text.
    """
    from aily.thinking.frameworks.mckinsey import McKinseyAnalyzer
    from aily.thinking.models import KnowledgePayload

    llm_client = context.get("llm_client")
    if not llm_client:
        return "Error: LLM client not available in context"

    analyzer = McKinseyAnalyzer(llm_client)
    payload = KnowledgePayload(content=text)

    try:
        result = await analyzer.analyze(payload)
        return _format_framework_result(result, "McKinsey")
    except Exception as e:
        return f"McKinsey analysis failed: {e}"


async def _gstack_agent_handler(context: dict[str, Any], text: str) -> str:
    """Handle GStack analyzer agent requests.

    Args:
        context: Agent context with dependencies.
        text: Content to analyze.

    Returns:
        GStack analysis results as formatted text.
    """
    from aily.thinking.frameworks.gstack import GStackAnalyzer
    from aily.thinking.models import KnowledgePayload

    llm_client = context.get("llm_client")
    if not llm_client:
        return "Error: LLM client not available in context"

    analyzer = GStackAnalyzer(llm_client)
    payload = KnowledgePayload(content=text)

    try:
        result = await analyzer.analyze(payload)
        return _format_framework_result(result, "GStack")
    except Exception as e:
        return f"GStack analysis failed: {e}"


async def _orchestrator_agent_handler(context: dict[str, Any], text: str) -> str:
    """Handle thinking orchestrator agent requests.

    Args:
        context: Agent context with dependencies.
        text: Content to analyze.

    Returns:
        Full analysis results as formatted text.
    """
    from aily.thinking.orchestrator import ThinkingOrchestrator
    from aily.thinking.models import KnowledgePayload

    llm_client = context.get("llm_client")
    graph_db = context.get("graph_db")

    if not llm_client:
        return "Error: LLM client not available in context"

    orchestrator = ThinkingOrchestrator(llm_client, graph_db)
    payload = KnowledgePayload(content=text)

    try:
        result = await orchestrator.think(payload)

        # Format summary
        lines = [
            f"# ARMY OF TOP MINDS Analysis",
            f"",
            f"**Confidence:** {result.confidence_score:.0%}",
            f"**Frameworks:** {', '.join(fi.framework_type.value for fi in result.framework_insights)}",
            f"**Insights:** {len(result.top_insights)}",
            f"",
            f"## Top Insights",
        ]

        for i, insight in enumerate(result.top_insights, 1):
            priority_emoji = {
                4: "🔴",
                3: "🟠",
                2: "🟡",
                1: "🟢",
            }.get(insight.priority.value, "⚪")
            lines.extend([
                f"",
                f"{i}. {priority_emoji} {insight.title}",
                f"   {insight.description}",
            ])

        if result.formatted_output:
            lines.extend([
                f"",
                f"## Output",
            ])
            for fmt, content in result.formatted_output.items():
                lines.append(f"**{fmt}:** Available")

        return "\n".join(lines)

    except Exception as e:
        return f"Analysis failed: {e}"


def _format_framework_result(result: Any, framework_name: str) -> str:
    """Format a framework result as readable text.

    Args:
        result: FrameworkInsight result.
        framework_name: Name of the framework.

    Returns:
        Formatted text output.
    """
    lines = [
        f"# {framework_name} Analysis",
        f"",
        f"**Confidence:** {result.confidence:.0%}",
        f"**Priority:** {result.priority.name}",
        f"",
        f"## Insights",
    ]

    for insight in result.insights:
        lines.append(f"- {insight}")

    return "\n".join(lines)
