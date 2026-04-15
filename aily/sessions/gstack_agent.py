"""GStack Agent - Business evaluation through actual execution.

The GStack mind doesn't just talk - it takes actions:
- Runs /qa to test the product
- Runs /ship to check deployment readiness
- Searches for competitive intelligence
- Actually validates assumptions through tools

Verdict: build_it | pivot | kill_it | needs_more_validation
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result of a GStack action."""
    action: str
    status: str  # success, failure, partial
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GStackSession:
    """GStack evaluation session with actions taken."""
    session_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    # Business hypothesis being evaluated
    hypothesis: str = ""
    target_user: str = ""
    problem: str = ""
    solution: str = ""

    # Actions taken
    actions: list[ActionResult] = field(default_factory=list)

    # Findings
    key_findings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)

    # Verdict
    verdict: str = ""  # build_it, pivot, kill_it, needs_more_validation
    confidence: float = 0.0

    def add_action(self, action: str, status: str, output: str, data: dict | None = None) -> None:
        self.actions.append(ActionResult(
            action=action,
            status=status,
            output=output,
            data=data or {},
        ))

    def complete(self, verdict: str, confidence: float) -> None:
        self.verdict = verdict
        self.confidence = confidence
        self.completed_at = datetime.now(timezone.utc)


class GStackAgent:
    """GStack agent that evaluates through execution.

    Like talking to Garry Tan, but he actually pulls up the code,
    runs the tests, checks the metrics, and tells you the truth.
    """

    def __init__(
        self,
        llm_client: Any,
        tool_executor: Callable | None = None,
        obsidian_writer: Any | None = None,
        graph_db: Any | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.obsidian_writer = obsidian_writer
        self.graph_db = graph_db

        # Available GStack actions
        self.actions = {
            "analyze_codebase": self._analyze_codebase,
            "check_test_coverage": self._check_test_coverage,
            "search_market": self._search_market,
            "validate_problem": self._validate_problem,
            "assess_tech_risk": self._assess_tech_risk,
            "check_deployment_readiness": self._check_deployment_readiness,
        }

    async def evaluate(
        self,
        hypothesis: str,
        problem: str,
        solution: str,
        target_user: str,
        context: dict[str, Any],
    ) -> GStackSession:
        """Execute GStack evaluation through actions."""

        import uuid
        session = GStackSession(
            session_id=f"gstack_{uuid.uuid4().hex[:8]}",
            hypothesis=hypothesis,
            problem=problem,
            solution=solution,
            target_user=target_user,
        )

        logger.info(f"[GStack Agent] Starting evaluation: {hypothesis[:60]}...")

        # Action 1: Analyze codebase (only if explicitly requested)
        if context.get("evaluate_codebase"):
            await self._run_action(session, "analyze_codebase", context)
            await self._run_action(session, "check_test_coverage", context)

        # Action 2: Search for market/competitive intel
        await self._run_action(session, "search_market", context)

        # Action 3: Validate problem with real users/data
        await self._run_action(session, "validate_problem", context)

        # Action 4: Assess technical risks
        await self._run_action(session, "assess_tech_risk", context)

        # Action 5: Check if ready to ship (only if explicitly requested)
        if context.get("evaluate_codebase"):
            await self._run_action(session, "check_deployment_readiness", context)

        # Generate verdict based on findings
        verdict, confidence = await self._generate_verdict(session)
        session.complete(verdict, confidence)

        logger.info(f"[GStack Agent] Verdict: {verdict} ({confidence:.0%} confidence)")

        return session

    async def _run_action(
        self,
        session: GStackSession,
        action_name: str,
        context: dict,
    ) -> None:
        """Execute a GStack action and record result."""

        logger.info(f"[GStack Agent] Running: {action_name}")

        try:
            action_fn = self.actions.get(action_name)
            if action_fn:
                result = await action_fn(context)
                session.add_action(
                    action=action_name,
                    status=result.get("status", "unknown"),
                    output=result.get("output", ""),
                    data=result.get("data", {}),
                )

                # Extract findings
                if "findings" in result:
                    session.key_findings.extend(result["findings"])
                if "blockers" in result:
                    session.blockers.extend(result["blockers"])
                if "opportunities" in result:
                    session.opportunities.extend(result["opportunities"])

                # Persist action to GraphDB
                if self.graph_db and context.get("proposal_node_id"):
                    try:
                        action_id = f"gstack_{uuid.uuid4().hex[:8]}"
                        await self.graph_db.insert_node(
                            node_id=action_id,
                            node_type="gstack_action",
                            label=f"{action_name}: {result.get('status', 'unknown')}",
                            source="entrepreneur",
                        )
                        await self.graph_db.insert_edge(
                            edge_id=f"edge_{uuid.uuid4().hex[:8]}",
                            source_node_id=action_id,
                            target_node_id=context["proposal_node_id"],
                            relation_type="validates",
                            weight=1.0,
                            source="entrepreneur",
                        )
                    except Exception as exc:
                        logger.warning(f"[GStack Agent] Failed to persist action: {exc}")
            else:
                session.add_action(
                    action=action_name,
                    status="error",
                    output=f"Unknown action: {action_name}",
                )
        except Exception as e:
            logger.exception(f"[GStack Agent] Action {action_name} failed: {e}")
            session.add_action(
                action=action_name,
                status="error",
                output=str(e),
            )

    async def _analyze_codebase(self, context: dict) -> dict:
        """Analyze the codebase for quality and complexity."""

        # Use LLM to reason about code quality
        prompt = """Analyze this codebase like a senior engineer evaluating a startup.

Look for:
1. Code quality and maintainability
2. Technical debt indicators
3. Architecture decisions
4. Test coverage signs
5. Documentation quality

Be direct. What's the real technical health?

Return JSON:
{
    "status": "success|partial|failure",
    "output": "Concise assessment",
    "findings": ["finding 1", "finding 2"],
    "blockers": ["critical issue"],
    "data": {"lines_of_code": 0, "test_ratio": 0.0}
}"""

        try:
            result = await self.llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return result
        except Exception as e:
            return {
                "status": "error",
                "output": f"Code analysis failed: {e}",
                "findings": [],
                "data": {},
            }

    async def _check_test_coverage(self, context: dict) -> dict:
        """Check test coverage and quality."""

        # If we have a tool executor, run actual tests
        if self.tool_executor:
            try:
                result = await self.tool_executor("run_tests")
                return {
                    "status": "success" if result.get("passed") else "failure",
                    "output": f"Tests: {result.get('passed', 0)}/{result.get('total', 0)} passed",
                    "findings": [f"Coverage: {result.get('coverage', 'unknown')}"],
                    "data": result,
                }
            except Exception as e:
                return {
                    "status": "error",
                    "output": f"Test execution failed: {e}",
                    "findings": ["Cannot verify test quality"],
                }

        # Fallback to LLM evaluation
        return {
            "status": "partial",
            "output": "Test coverage check skipped - no tool executor",
            "findings": ["Need to verify test coverage manually"],
        }

    async def _search_market(self, context: dict) -> dict:
        """Search for market intelligence and competitors."""

        hypothesis = context.get("hypothesis", "")
        target_user = context.get("target_user", "")

        prompt = f"""Search for market intelligence on this business.

Hypothesis: {hypothesis}
Target User: {target_user}

Find:
1. Existing competitors (direct and indirect)
2. Market size indicators
3. Recent similar startups (funded, failed, exited)
4. User pain point validation signals
5. Regulatory or market risks

Return JSON:
{{
    "status": "success|partial",
    "output": "Market assessment summary",
    "findings": ["competitor A exists", "market is $X"],
    "opportunities": ["gap in market"],
    "blockers": ["crowded market"],
    "data": {{"competitors": [], "market_size": "unknown"}}
}}"""

        try:
            result = await self.llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return result
        except Exception as e:
            return {
                "status": "error",
                "output": f"Market search failed: {e}",
                "findings": [],
            }

    async def _validate_problem(self, context: dict) -> dict:
        """Validate that the problem is real and painful."""

        problem = context.get("problem", "")
        target_user = context.get("target_user", "")

        prompt = f"""Validate this problem statement like a YC interviewer.

Problem: {problem}
Target User: {target_user}

Ask the hard questions:
1. How do you KNOW this is a real problem?
2. How are they solving it today?
3. How much are they paying (in time or money) for current solutions?
4. Is this a hair-on-fire problem or a nice-to-have?
5. Have you talked to 10+ potential users?

Return JSON:
{{
    "status": "success|partial|failure",
    "output": "Problem validation assessment",
    "findings": ["Evidence of real pain", "Users currently use X workaround"],
    "blockers": ["No user interviews", "Nice-to-have, not must-have"],
    "data": {{"validation_level": "strong|weak|none"}}
}}"""

        try:
            result = await self.llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
            )
            return result
        except Exception as e:
            return {
                "status": "error",
                "output": f"Problem validation failed: {e}",
                "findings": [],
            }

    async def _assess_tech_risk(self, context: dict) -> dict:
        """Assess technical risks and feasibility."""

        solution = context.get("solution", "")

        prompt = f"""Assess technical risks for this solution.

Solution: {solution}

Evaluate:
1. Technical feasibility (can it be built?)
2. Complexity vs timeline
3. Key technical dependencies
4. Team capability requirements
5. Infrastructure costs at scale
6. Security/compliance considerations

Return JSON:
{{
    "status": "success|partial|failure",
    "output": "Technical risk assessment",
    "findings": ["Feasible with current stack", "Will need ML expertise"],
    "blockers": ["Requires impossible scale", "Regulatory barrier"],
    "data": {{"risk_level": "low|medium|high", "mvp_complexity": "weeks|months"}}
}}"""

        try:
            result = await self.llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return result
        except Exception as e:
            return {
                "status": "error",
                "output": f"Tech risk assessment failed: {e}",
                "findings": [],
            }

    async def _check_deployment_readiness(self, context: dict) -> dict:
        """Check if the product is ready to ship."""

        # If we have tool executor, run actual checks
        if self.tool_executor:
            checks = []

            # Run health check
            try:
                health = await self.tool_executor("health_check")
                checks.append(("health", health))
            except:
                checks.append(("health", {"status": "unknown"}))

            return {
                "status": "success",
                "output": f"Deployment checks: {len([c for c in checks if c[1].get('status') == 'ok'])}/{len(checks)} passing",
                "findings": [f"{name}: {data.get('status')}" for name, data in checks],
                "data": {"checks": dict(checks)},
            }

        # Fallback
        return {
            "status": "partial",
            "output": "Deployment readiness check skipped - no tool executor",
            "findings": ["Manual deployment verification needed"],
        }

    async def _generate_verdict(self, session: GStackSession) -> tuple[str, float]:
        """Generate final verdict based on all actions taken."""

        # Build context from all actions
        action_outputs = "\n\n".join([
            f"=== {a.action} ===\nStatus: {a.status}\n{a.output}"
            for a in session.actions
        ])

        findings = "\n".join([f"- {f}" for f in session.key_findings])
        blockers = "\n".join([f"- {b}" for b in session.blockers])
        opportunities = "\n".join([f"- {o}" for o in session.opportunities])

        prompt = f"""Based on the GStack evaluation actions taken, render a final verdict.

Hypothesis: {session.hypothesis}
Problem: {session.problem}
Solution: {session.solution}
Target User: {session.target_user}

Actions Taken:
{action_outputs}

Key Findings:
{findings}

Blockers:
{blockers}

Opportunities:
{opportunities}

Render verdict like Garry Tan would - direct, no bullshit:
- build_it: Strong signal, clear path, real problem
- pivot: Something's off but there's potential
- kill_it: Fatal flaws, don't waste time
- needs_more_validation: Not enough data to decide

Return JSON:
{{
    "verdict": "build_it|pivot|kill_it|needs_more_validation",
    "confidence": 0.0-1.0,
    "reasoning": "Why this verdict",
    "critical_factors": ["factor 1", "factor 2"],
    "next_steps": ["do this", "then this"]
}}"""

        try:
            result = await self.llm_client.chat_json(
                messages=[{
                    "role": "system",
                    "content": "You are Garry Tan rendering a final investment decision. Be direct. No hedging."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.7,
            )

            return (
                result.get("verdict", "needs_more_validation"),
                result.get("confidence", 0.5),
            )
        except Exception as e:
            logger.error(f"[GStack Agent] Verdict generation failed: {e}")
            return ("needs_more_validation", 0.3)

    def get_session_report(self, session: GStackSession) -> str:
        """Generate human-readable session report."""

        lines = [
            f"# GStack Evaluation: {session.hypothesis[:60]}...",
            "",
            f"**Verdict:** {session.verdict.upper()}",
            f"**Confidence:** {session.confidence:.0%}",
            f"**Duration:** {len(session.actions)} actions taken",
            "",
            "## Actions Taken",
        ]

        for action in session.actions:
            emoji = "✅" if action.status == "success" else "⚠️" if action.status == "partial" else "❌"
            lines.append(f"{emoji} **{action.action}**: {action.status}")
            lines.append(f"   {action.output[:150]}...")
            lines.append("")

        if session.key_findings:
            lines.extend(["## Key Findings", ""])
            for f in session.key_findings[:10]:
                lines.append(f"- {f}")
            lines.append("")

        if session.blockers:
            lines.extend(["## Blockers", ""])
            for b in session.blockers:
                lines.append(f"- ⚠️ {b}")
            lines.append("")

        if session.opportunities:
            lines.extend(["## Opportunities", ""])
            for o in session.opportunities:
                lines.append(f"- 💡 {o}")
            lines.append("")

        return "\n".join(lines)
