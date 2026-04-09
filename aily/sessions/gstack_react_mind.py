"""GStack ReAct Mind - Entrepreneurial thinking like talking to Garry Tan.

This isn't a rigid analyzer - it's a conversation. The GStack mind:
- Asks clarifying questions when things are unclear
- Thinks out loud about what matters for the business
- Iterates on understanding before proposing
- Talks like a human (direct, concrete, occasionally profane)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from aily.sessions.react_base import ReActMind, ReActSession, Action, ActionType

logger = logging.getLogger(__name__)


class GStackReactMind(ReActMind):
    """GStack mind that thinks and talks like Garry Tan.

    Key traits:
    - Direct and concrete, no MBA-speak
    - Obsessive about "what does the user want"
    - Pushes toward shipping and getting feedback
    - Asks "is this a real problem?" constantly
    - Values speed and iteration over perfect planning
    """

    def __init__(self, llm_client: Any, min_confidence: float = 0.75) -> None:
        super().__init__(
            llm_client=llm_client,
            mind_name="gstack",
            max_iterations=8,
            min_confidence=min_confidence,
        )
        # Track conversation state
        self._clarifying_questions_asked: list[str] = []
        self._business_insights: list[dict] = []

    async def _think(self, session: ReActSession, context: dict) -> dict:
        """Think like Garry - what's the real opportunity here?"""

        knowledge = context.get("knowledge", [])
        previous_thoughts = session.thoughts
        previous_qa = context.get("qa_history", [])

        # Build the thinking prompt
        prompt = self._build_thinking_prompt(knowledge, previous_thoughts, previous_qa, context)

        try:
            response = await self.llm_client.chat_json(
                messages=[
                    {
                        "role": "system",
                        "content": """You are Garry Tan in a conversation about a startup idea.

Your personality:
- Direct and concrete. No "leverage" or "synergy" bullshit
- Obsessive about "what does the user actually want"
- Push toward shipping and getting real feedback
- Ask hard questions: "Is this a real problem?" "Who wants this?"
- Value speed over perfect planning
- Occasionally say things like "This is the whole game" or "That's it."

When thinking:
1. Be conversational - you're thinking out loud
2. If something's unclear, say so and ask a clarifying question
3. Identify the real risk/uncertainty
4. Judge confidence honestly (0.0 to 1.0)

Return JSON:
{
    "thinking": "your raw thought process, like you're talking to a founder",
    "reasoning_type": "problem_validation|market_sizing|growth_loop|risk_assessment|go_to_market",
    "confidence": 0.0-1.0,
    "complete": false,
    "needs_clarification": false,
    "clarifying_question": "if unclear, what do you need to know?"
}"""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
            )

            return {
                "content": response.get("thinking", "Need to think more..."),
                "type": response.get("reasoning_type", "general"),
                "confidence": response.get("confidence", 0.0),
                "complete": response.get("complete", False),
                "needs_clarification": response.get("needs_clarification", False),
                "clarifying_question": response.get("clarifying_question", ""),
            }

        except Exception as e:
            logger.error(f"[GStack] Thinking failed: {e}")
            return {
                "content": "Something's off. Let me ask - what exactly are we building here?",
                "type": "general",
                "confidence": 0.3,
                "complete": False,
                "needs_clarification": True,
                "clarifying_question": "What is the core problem you're solving?",
            }

    async def _decide_action(self, session: ReActSession, context: dict) -> dict:
        """Decide what to do next based on current thinking."""

        last_thought = session.thoughts[-1] if session.thoughts else None

        if last_thought and getattr(last_thought, 'needs_clarification', False):
            return {
                "type": "question",
                "description": "Need to understand the problem better before analyzing",
                "parameters": {
                    "question": getattr(last_thought, 'clarifying_question', 'What is the core problem?'),
                    "reasoning": "Can't evaluate business without knowing what problem we're solving"
                }
            }

        # Decide based on what we know
        thought_count = len(session.thoughts)

        if thought_count == 1:
            return {
                "type": "search",
                "description": "Look for similar problems/solutions in knowledge base",
                "parameters": {"query": "market validation precedents"}
            }
        elif thought_count == 2:
            return {
                "type": "analyze",
                "description": "Deep analysis of PMF indicators",
                "parameters": {"framework": "pmf_validation"}
            }
        elif thought_count == 3:
            return {
                "type": "analyze",
                "description": "Map growth loops and acquisition channels",
                "parameters": {"framework": "growth_loops"}
            }
        elif thought_count >= 4:
            return {
                "type": "propose",
                "description": "Generate concrete business proposal",
                "parameters": {"format": "gstack_memo"}
            }

        return {
            "type": "think",
            "description": "Continue reasoning",
            "parameters": {}
        }

    async def _execute_action(self, action: Action, context: dict) -> Any:
        """Execute the action."""

        if action.action_type == ActionType.QUESTION:
            # Record the question
            question = action.parameters.get("question", "")
            self._clarifying_questions_asked.append(question)
            return {
                "type": "question_asked",
                "question": question,
                "awaiting_answer": True,
            }

        elif action.action_type == ActionType.SEARCH:
            # Search knowledge base for precedents
            knowledge = context.get("knowledge", [])
            # Simple keyword matching for now
            relevant = [k for k in knowledge if any(
                word in str(k).lower()
                for word in ["market", "user", "problem", "solution", "revenue"]
            )]
            return {
                "type": "search_results",
                "items_found": len(relevant),
                "relevant_knowledge": relevant[:5],
            }

        elif action.action_type == ActionType.ANALYZE:
            framework = action.parameters.get("framework", "")
            knowledge = context.get("knowledge", [])

            # Run framework-specific analysis
            prompt = f"""Analyze this startup opportunity using {framework}.

Knowledge:
{self._format_knowledge(knowledge)}

Think like Garry Tan. Be direct about:
1. What's the real user pain?
2. Is anyone actually desperate for this?
3. How do you get your first 100 users?
4. What kills this idea?

Return JSON with:
- "analysis": your concrete assessment
- "red_flags": list of real concerns
- "bright_spots": what genuinely looks good
- "confidence": 0.0-1.0
"""
            try:
                result = await self.llm_client.chat_json(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                self._business_insights.append({
                    "framework": framework,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **result
                })
                return result
            except Exception as e:
                return {"error": str(e), "framework": framework}

        elif action.action_type == ActionType.PROPOSE:
            # Generate final proposal
            insights = self._business_insights
            return {
                "type": "proposal",
                "insights": insights,
                "ready": len(insights) >= 2,
            }

        return {"type": "unknown_action"}

    async def _observe(self, result: Any, context: dict) -> dict:
        """Observe and interpret action results."""

        if isinstance(result, dict):
            if result.get("type") == "question_asked":
                return {
                    "content": f"Asked clarifying question: {result.get('question')}",
                    "data": {"awaiting_user_input": True}
                }
            elif result.get("type") == "search_results":
                items = result.get("items_found", 0)
                return {
                    "content": f"Found {items} relevant knowledge items. Looking at precedents...",
                    "data": {"relevant_count": items}
                }
            elif result.get("type") == "proposal":
                ready = result.get("ready", False)
                return {
                    "content": "Business proposal framework complete" if ready else "Need more analysis before proposing",
                    "data": {"proposal_ready": ready}
                }
            elif "analysis" in result:
                return {
                    "content": f"Analysis complete: {result.get('analysis', '')[:200]}...",
                    "data": {
                        "red_flags": result.get("red_flags", []),
                        "bright_spots": result.get("bright_spots", []),
                        "confidence": result.get("confidence", 0.0),
                    }
                }

        return {
            "content": f"Action completed with result: {str(result)[:200]}",
            "data": {"raw_result": result}
        }

    def _build_thinking_prompt(self, knowledge: list, previous_thoughts: list, qa_history: list, context: dict) -> str:
        """Build the thinking prompt with context."""

        lines = ["I'm looking at a potential startup opportunity. Let me think through this...", ""]

        if knowledge:
            lines.append("**What I know:**")
            for item in knowledge[:5]:
                content = str(item.get("content", item))[:200]
                lines.append(f"- {content}...")
            lines.append("")

        if previous_thoughts:
            lines.append("**What I've thought so far:**")
            for t in previous_thoughts[-2:]:
                lines.append(f"- {t.content[:150]}...")
            lines.append("")

        if qa_history:
            lines.append("**Questions I've asked:**")
            for qa in qa_history:
                lines.append(f"Q: {qa.get('question', '')}")
                lines.append(f"A: {qa.get('answer', '')}")
            lines.append("")

        lines.append("**Now I need to figure out:**")
        lines.append("- Is this a real problem people have?")
        lines.append("- Who desperately needs this solution?")
        lines.append("- Can we build it and get it to them fast?")
        lines.append("")

        return "\n".join(lines)

    def _format_knowledge(self, knowledge: list) -> str:
        """Format knowledge for prompts."""
        if not knowledge:
            return "No prior knowledge"
        return "\n".join([
            f"- {str(k.get('content', k))[:150]}..."
            for k in knowledge[:10]
        ])

    async def generate_final_proposal(self, session: ReActSession) -> dict:
        """Generate the final business proposal after ReAct reasoning."""

        insights = self._business_insights
        transcript = self.get_session_transcript(session)

        prompt = f"""Based on the following ReAct reasoning session, generate a concrete business proposal.

ReAct Transcript:
{transcript}

Key Insights:
{json.dumps(insights, indent=2)}

Write this like Garry Tan talking to a founder. Direct, concrete, actionable.

Return JSON:
{{
    "title": "Short, punchy title",
    "one_liner": "What this is in one sentence",
    "problem": "The real problem being solved",
    "solution": "The solution",
    "target_user": "Who desperately needs this",
    "why_now": "Why is timing right?",
    "risks": ["Real risks that could kill this"],
    "next_steps": ["Concrete actions for next 2 weeks"],
    "confidence": 0.0-1.0,
    "verdict": "build_it|pivot|kill_it|needs_more_validation"
}}"""

        try:
            result = await self.llm_client.chat_json(
                messages=[{
                    "role": "system",
                    "content": "You are Garry Tan writing a business evaluation memo. Be direct. No fluff."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.7,
            )
            return result
        except Exception as e:
            logger.error(f"[GStack] Proposal generation failed: {e}")
            return {
                "title": "Analysis Incomplete",
                "one_liner": "Could not complete business evaluation",
                "verdict": "needs_more_validation",
                "error": str(e),
            }
