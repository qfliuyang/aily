"""TRIZ ReAct Mind - Systematic innovation through contradiction resolution.

TRIZ (Theory of Inventive Problem Solving) ReAct pattern:
1. Identify technical contradictions in the problem
2. Map to 40 Inventive Principles
3. Search separation principles
4. Generate inventive solutions
5. Iterate on solution quality
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aily.sessions.react_base import ReActMind, ReActSession, Action, ActionType

logger = logging.getLogger(__name__)


class TrizReactMind(ReActMind):
    """TRIZ mind that reasons through contradictions to find inventive solutions.

    ReAct loop:
    - Thought: "What are we trying to improve? What gets worse?"
    - Action: Map contradiction to TRIZ matrix
    - Observation: "Principles X, Y, Z apply"
    - Thought: "How can we apply principle X?"
    - Repeat until solution converges
    """

    # The 40 TRIZ principles (abbreviated for prompting)
    TRIZ_PRINCIPLES = {
        1: "Segmentation", 2: "Taking out", 3: "Local quality",
        4: "Asymmetry", 5: "Merging", 6: "Universality",
        7: "Nested doll", 8: "Anti-weight", 9: "Preliminary anti-action",
        10: "Preliminary action", 11: "Beforehand cushioning",
        12: "Equipotentiality", 13: "The other way around",
        14: "Curvature", 15: "Dynamics", 16: "Partial or excessive actions",
        17: "Another dimension", 18: "Mechanical vibration",
        19: "Periodic action", 20: "Continuity of useful action",
        21: "Skipping", 22: "Blessing in disguise",
        23: "Feedback", 24: "Intermediary", 25: "Self-service",
        26: "Copying", 27: "Cheap short-living objects",
        28: "Mechanics substitution", 29: "Pneumatics and hydraulics",
        30: "Flexible shells", 31: "Porous materials",
        32: "Color changes", 33: "Homogeneity",
        34: "Discarding and recovering", 35: "Parameter changes",
        36: "Phase transitions", 37: "Thermal expansion",
        38: "Strong oxidants", 39: "Inert atmosphere",
        40: "Composite materials"
    }

    # Common engineering parameters for contradiction mapping
    ENGINEERING_PARAMETERS = [
        "Weight of moving object", "Weight of stationary object",
        "Length of moving object", "Length of stationary object",
        "Area of moving object", "Area of stationary object",
        "Volume of moving object", "Volume of stationary object",
        "Speed", "Force", "Tension/pressure", "Shape",
        "Stability", "Strength", "Durability", "Temperature",
        "Brightness", "Energy spent", "Power", "Noise",
        "Harmful emissions", "Information loss", "Waste of time",
        "Amount of substance", "Reliability", "Accuracy",
        "Complexity", "Difficulty of repair", "Adaptability",
        "Device complexity", "Control complexity", "Level of automation",
        "Productivity", "Operating time", "Repair time",
        "Flow rate", "Loss of information", "Waste of energy",
        "Substance waste", "Harmful side effects"
    ]

    def __init__(self, llm_client: Any, min_confidence: float = 0.75) -> None:
        super().__init__(
            llm_client=llm_client,
            mind_name="triz",
            max_iterations=10,
            min_confidence=min_confidence,
        )
        self._contradictions_found: list[dict] = []
        self._principles_applied: list[int] = []
        self._solutions_generated: list[dict] = []

    async def _think(self, session: ReActSession, context: dict) -> dict:
        """Think through the TRIZ methodology step by step."""

        knowledge = context.get("knowledge", [])
        step = session.current_step

        # Progress through TRIZ stages
        if step == 1:
            # Step 1: Understand the system
            prompt = self._build_system_analysis_prompt(knowledge)
            reasoning_type = "system_analysis"
        elif step == 2:
            # Step 2: Identify ideal final result (IFR)
            prompt = self._build_ifr_prompt(knowledge, session.thoughts[0] if session.thoughts else None)
            reasoning_type = "ideal_final_result"
        elif step == 3:
            # Step 3: Find contradictions
            prompt = self._build_contradiction_prompt(session.thoughts)
            reasoning_type = "contradiction_identification"
        elif step == 4 and self._contradictions_found:
            # Step 4: Map to TRIZ matrix
            prompt = self._build_matrix_prompt(self._contradictions_found[-1])
            reasoning_type = "matrix_mapping"
        elif len(self._principles_applied) > 0:
            # Step 5+: Apply principles and iterate
            prompt = self._build_solution_prompt(session)
            reasoning_type = "solution_generation"
        else:
            # General reasoning
            prompt = self._build_general_prompt(session)
            reasoning_type = "general"

        try:
            response = await self.llm_client.chat_json(
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a TRIZ (Theory of Inventive Problem Solving) expert.

Your job is to systematically find inventive solutions by:
1. Understanding the technical system
2. Defining the Ideal Final Result (IFR)
3. Identifying technical contradictions (what improves vs what worsens)
4. Mapping contradictions to TRIZ matrix
5. Applying the 40 Inventive Principles

The 40 TRIZ Principles:
{json.dumps(self.TRIZ_PRINCIPLES, indent=2)}

Engineering Parameters for Contradictions:
{json.dumps(self.ENGINEERING_PARAMETERS, indent=2)}

Think step by step. Be specific about:
- What parameter we're trying to improve
- What parameter gets worse as a result
- Which TRIZ principles apply
- How to apply them concretely

Return JSON:
{{
    "thinking": "detailed reasoning",
    "reasoning_type": "system_analysis|ideal_final_result|contradiction_identification|matrix_mapping|solution_generation",
    "confidence": 0.0-1.0,
    "complete": false,
    "next_step": "what to do next",
    "contradictions_found": [{{"improving": "param", "worsening": "param", "description": ""}}],
    "principles_suggested": [1, 15, 35],
    "solution_ideas": ["idea 1", "idea 2"]
}}"""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )

            # Store contradictions if found
            if "contradictions_found" in response:
                self._contradictions_found.extend(response["contradictions_found"])
            if "principles_suggested" in response:
                self._principles_applied.extend(response["principles_suggested"])

            return {
                "content": response.get("thinking", "Analyzing system..."),
                "type": response.get("reasoning_type", reasoning_type),
                "confidence": response.get("confidence", 0.0),
                "complete": response.get("complete", False),
                "contradictions_found": response.get("contradictions_found", []),
                "principles_suggested": response.get("principles_suggested", []),
                "solution_ideas": response.get("solution_ideas", []),
            }

        except Exception as e:
            logger.error(f"[TRIZ] Thinking failed: {e}")
            return {
                "content": f"Error in TRIZ analysis: {e}. Let me reconsider the approach.",
                "type": "error_recovery",
                "confidence": 0.3,
                "complete": False,
            }

    async def _decide_action(self, session: ReActSession, context: dict) -> dict:
        """Decide next TRIZ action based on current state."""

        step = session.current_step

        if step == 1:
            return {
                "type": "search",
                "description": "Search for similar systems and solutions in knowledge base",
                "parameters": {"query": "system patterns precedents"}
            }
        elif step == 2:
            return {
                "type": "analyze",
                "description": "Define Ideal Final Result",
                "parameters": {"framework": "ideal_final_result"}
            }
        elif step == 3:
            return {
                "type": "analyze",
                "description": "Identify technical contradictions",
                "parameters": {"framework": "contradiction_matrix"}
            }
        elif step == 4 and self._contradictions_found:
            return {
                "type": "analyze",
                "description": f"Map contradiction to TRIZ matrix: {self._contradictions_found[-1].get('improving')} vs {self._contradictions_found[-1].get('worsening')}",
                "parameters": {
                    "framework": "triz_matrix",
                    "contradiction": self._contradictions_found[-1]
                }
            }
        elif self._principles_applied:
            principle = self._principles_applied[-1]
            return {
                "type": "analyze",
                "description": f"Apply TRIZ Principle {principle}: {self.TRIZ_PRINCIPLES.get(principle, 'Unknown')}",
                "parameters": {
                    "framework": "principle_application",
                    "principle_number": principle,
                    "principle_name": self.TRIZ_PRINCIPLES.get(principle, "Unknown")
                }
            }

        return {
            "type": "propose",
            "description": "Generate final inventive solution",
            "parameters": {"format": "triz_solution"}
        }

    async def _execute_action(self, action: Action, context: dict) -> Any:
        """Execute TRIZ-specific actions."""

        if action.action_type == ActionType.SEARCH:
            # Search knowledge base
            knowledge = context.get("knowledge", [])
            relevant = [k for k in knowledge if any(
                word in str(k).lower()
                for word in ["problem", "solution", "system", "improve", "trade-off"]
            )]
            return {
                "type": "search_results",
                "items_found": len(relevant),
                "relevant_knowledge": relevant[:5],
            }

        elif action.action_type == ActionType.ANALYZE:
            framework = action.parameters.get("framework", "")

            if framework == "ideal_final_result":
                # Define IFR
                return {
                    "type": "ifr_definition",
                    "ifr": "System performs function by itself without harmful effects",
                    "barriers": ["Current implementation requires X", "Resource limitation Y"],
                }

            elif framework == "contradiction_matrix":
                # Return contradiction mapping
                contradictions = self._contradictions_found
                return {
                    "type": "contradictions_mapped",
                    "contradictions": contradictions,
                    "suggested_principles": [1, 15, 28, 35],  # Common inventive principles
                }

            elif framework == "principle_application":
                principle = action.parameters.get("principle_number", 0)
                return {
                    "type": "principle_applied",
                    "principle": principle,
                    "principle_name": self.TRIZ_PRINCIPLES.get(principle, "Unknown"),
                    "application_ideas": self._generate_principle_applications(principle),
                }

            return {"type": "analysis_complete", "framework": framework}

        elif action.action_type == ActionType.PROPOSE:
            # Generate solution proposal
            return {
                "type": "solution_proposed",
                "contradictions_resolved": len(self._contradictions_found),
                "principles_used": list(set(self._principles_applied)),
                "ready": len(self._contradictions_found) > 0 and len(self._principles_applied) > 0,
            }

        return {"type": "unknown_action"}

    async def _observe(self, result: Any, context: dict) -> dict:
        """Observe action results and interpret for TRIZ."""

        if isinstance(result, dict):
            result_type = result.get("type", "")

            if result_type == "search_results":
                return {
                    "content": f"Found {result.get('items_found', 0)} relevant precedents. Can learn from similar systems.",
                    "data": {"precedents": result.get("relevant_knowledge", [])}
                }

            elif result_type == "ifr_definition":
                return {
                    "content": f"Ideal Final Result defined: {result.get('ifr', '')}. Barriers: {result.get('barriers', [])}",
                    "data": {"ifr": result.get("ifr"), "barriers": result.get("barriers", [])}
                }

            elif result_type == "contradictions_mapped":
                contradictions = result.get("contradictions", [])
                principles = result.get("suggested_principles", [])
                return {
                    "content": f"Found {len(contradictions)} contradictions. Suggested principles: {[self.TRIZ_PRINCIPLES.get(p, p) for p in principles[:3]]}",
                    "data": {
                        "contradictions": contradictions,
                        "suggested_principles": principles,
                    }
                }

            elif result_type == "principle_applied":
                principle = result.get("principle_name", "")
                ideas = result.get("application_ideas", [])
                return {
                    "content": f"Applied {principle}. Generated {len(ideas)} application ideas.",
                    "data": {"principle": principle, "ideas": ideas}
                }

            elif result_type == "solution_proposed":
                ready = result.get("ready", False)
                return {
                    "content": "Solution ready for finalization" if ready else "Need more iteration on solution",
                    "data": {
                        "ready": ready,
                        "contradictions_resolved": result.get("contradictions_resolved", 0),
                        "principles_used": result.get("principles_used", []),
                    }
                }

        return {
            "content": f"Action completed: {str(result)[:200]}",
            "data": {"raw": result}
        }

    def _generate_principle_applications(self, principle: int) -> list[str]:
        """Generate concrete application ideas for a TRIZ principle."""
        applications = {
            1: ["Divide system into independent parts", "Make parts modular", "Enable partial replacement"],
            15: ["Make system adjustable", "Allow dynamic reconfiguration", "Enable parameter changes"],
            35: ["Change temperature/pressure", "Modify material state", "Adjust chemical composition"],
            28: ["Replace mechanical with optical", "Use electromagnetic fields", "Apply ultrasound"],
            2: ["Extract interfering part", "Remove unnecessary elements", "Isolate harmful factors"],
        }
        return applications.get(principle, ["Apply principle creatively", "Look for analogous solutions"])

    def _build_system_analysis_prompt(self, knowledge: list) -> str:
        return f"""Analyze this system for TRIZ innovation potential.

Knowledge:
{self._format_knowledge(knowledge)}

What is the core technical system? What function does it perform?
What are the main components and their interactions?"""

    def _build_ifr_prompt(self, knowledge: list, prev_thought: Any) -> str:
        return """Define the Ideal Final Result (IFR) for this system.

The IFR is:
- The system performs the useful function
- WITHOUT the harmful effects
- WITHOUT complex mechanisms
- Resources are used efficiently

What would perfection look like?"""

    def _build_contradiction_prompt(self, thoughts: list) -> str:
        return """Identify technical contradictions.

When we try to improve something, what gets worse?

Common contradiction patterns:
- Speed vs Accuracy
- Strength vs Weight
- Power vs Energy consumption
- Feature richness vs Simplicity

What are the specific engineering parameters in conflict?"""

    def _build_matrix_prompt(self, contradiction: dict) -> str:
        improving = contradiction.get("improving", "Parameter A")
        worsening = contradiction.get("worsening", "Parameter B")
        return f"""Map this contradiction to TRIZ principles:

Improving: {improving}
Worsening: {worsening}

Which of the 40 TRIZ Inventive Principles would help resolve this contradiction?
Consider: Segmentation, Dynamics, Parameter Changes, Mechanics Substitution..."""

    def _build_solution_prompt(self, session: ReActSession) -> str:
        principles = [self.TRIZ_PRINCIPLES.get(p, p) for p in self._principles_applied[-3:]]
        return f"""Generate concrete inventive solutions using these TRIZ principles:
{principles}

How can we apply these principles to solve the contradictions we found?
Be specific about implementation."""

    def _build_general_prompt(self, session: ReActSession) -> str:
        return "Continue TRIZ analysis. What should we examine next?"

    def _format_knowledge(self, knowledge: list) -> str:
        if not knowledge:
            return "No prior knowledge"
        return "\n".join([
            f"- {str(k.get('content', k))[:150]}..."
            for k in knowledge[:10]
        ])

    async def generate_final_proposal(self, session: ReActSession) -> dict:
        """Generate final TRIZ innovation proposal."""

        transcript = self.get_session_transcript(session)
        contradictions = self._contradictions_found
        principles = list(set(self._principles_applied))

        prompt = f"""Based on this TRIZ ReAct session, generate a final innovation proposal.

ReAct Transcript:
{transcript}

Contradictions Identified:
{json.dumps(contradictions, indent=2)}

TRIZ Principles Applied:
{[f"{p}: {self.TRIZ_PRINCIPLES.get(p, 'Unknown')}" for p in principles]}

Return JSON:
{{
    "title": "Inventive solution title",
    "problem_statement": "The core contradiction",
    "contradiction": {{"improving": "X", "worsening": "Y"}},
    "triz_principles_applied": [1, 15, 35],
    "inventive_solution": "Concrete solution description",
    "how_it_works": "Technical explanation",
    "benefits": ["benefit 1", "benefit 2"],
    "implementation_complexity": "low|medium|high",
    "confidence": 0.0-1.0,
    "novelty_score": 0.0-1.0
}}"""

        try:
            result = await self.llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return result
        except Exception as e:
            logger.error(f"[TRIZ] Proposal generation failed: {e}")
            return {
                "title": "TRIZ Analysis Incomplete",
                "problem_statement": "Could not complete analysis",
                "error": str(e),
                "confidence": 0.0,
            }
