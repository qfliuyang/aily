"""ReAct (Reasoning + Acting) framework for Three-Mind System.

ReAct pattern: Thought -> Action -> Observation -> Repeat
Minds don't just analyze - they think, take actions, observe results, and iterate.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions a mind can take."""
    THINK = auto()      # Internal reasoning
    SEARCH = auto()     # Query knowledge graph
    ANALYZE = auto()    # Run framework analysis
    QUESTION = auto()   # Ask for clarification
    PROPOSE = auto()    # Generate proposal
    VALIDATE = auto()   # Check proposal quality
    REFLECT = auto()    # Self-reflection on output


@dataclass
class Thought:
    """A reasoning step in the ReAct loop."""
    step_number: int
    content: str
    reasoning_type: str = "general"  # contradiction, opportunity, risk, etc.
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Action:
    """An action taken by the mind."""
    step_number: int
    action_type: ActionType
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Observation:
    """Result observed from an action."""
    step_number: int
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReActSession:
    """Complete ReAct reasoning session."""
    session_id: str
    mind_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    thoughts: list[Thought] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    max_iterations: int = 10

    @property
    def current_step(self) -> int:
        return max(len(self.thoughts), len(self.actions), len(self.observations)) + 1

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None

    def add_thought(self, content: str, reasoning_type: str = "general", confidence: float = 0.0) -> Thought:
        thought = Thought(
            step_number=self.current_step,
            content=content,
            reasoning_type=reasoning_type,
            confidence=confidence,
        )
        self.thoughts.append(thought)
        return thought

    def add_action(self, action_type: ActionType, description: str, parameters: dict | None = None, result: Any = None) -> Action:
        action = Action(
            step_number=self.current_step,
            action_type=action_type,
            description=description,
            parameters=parameters or {},
            result=result,
        )
        self.actions.append(action)
        return action

    def add_observation(self, content: str, data: dict | None = None) -> Observation:
        obs = Observation(
            step_number=self.current_step,
            content=content,
            data=data or {},
        )
        self.observations.append(obs)
        return obs

    def complete(self) -> None:
        self.completed_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "mind_name": self.mind_name,
            "steps": self.current_step - 1,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "thoughts": [{"step": t.step_number, "type": t.reasoning_type, "content": t.content[:200]} for t in self.thoughts],
            "actions": [{"step": a.step_number, "type": a.action_type.name, "description": a.description} for a in self.actions],
        }


class ReActMind(ABC):
    """Base class for ReAct-powered minds.

    Minds using ReAct don't just analyze - they:
    1. THINK: Reason about what they know and what to do
    2. ACT: Take actions (search, analyze, question)
    3. OBSERVE: Look at results
    4. REPEAT: Iterate until confident
    """

    def __init__(
        self,
        llm_client: Any,
        mind_name: str,
        max_iterations: int = 10,
        min_confidence: float = 0.7,
    ) -> None:
        self.llm_client = llm_client
        self.mind_name = mind_name
        self.max_iterations = max_iterations
        self.min_confidence = min_confidence
        self._current_session: ReActSession | None = None

    async def run_react_session(self, context: dict[str, Any]) -> ReActSession:
        """Run a complete ReAct reasoning session.

        Args:
            context: Initial context (knowledge, previous outputs, etc.)

        Returns:
            Complete ReAct session with all thoughts, actions, observations
        """
        import uuid
        session = ReActSession(
            session_id=f"{self.mind_name}_{uuid.uuid4().hex[:8]}",
            mind_name=self.mind_name,
            max_iterations=self.max_iterations,
        )
        self._current_session = session

        logger.info(f"[{self.mind_name}] Starting ReAct session {session.session_id}")

        try:
            for iteration in range(self.max_iterations):
                # STEP 1: THINK
                thought = await self._think(session, context)
                session.add_thought(thought["content"], thought.get("type", "general"), thought.get("confidence", 0.0))
                logger.debug(f"[{self.mind_name}] Thought {iteration+1}: {thought['content'][:100]}...")

                # Check if we should stop
                if thought.get("complete", False) or thought.get("confidence", 0.0) >= self.min_confidence:
                    logger.info(f"[{self.mind_name}] ReAct complete at iteration {iteration+1}")
                    break

                # STEP 2: ACT
                action_plan = await self._decide_action(session, context)
                action = session.add_action(
                    action_type=ActionType[action_plan["type"].upper()],
                    description=action_plan["description"],
                    parameters=action_plan.get("parameters", {}),
                )

                # STEP 3: EXECUTE ACTION
                result = await self._execute_action(action, context)
                action.result = result

                # STEP 4: OBSERVE
                observation = await self._observe(result, context)
                session.add_observation(observation["content"], observation.get("data", {}))

                logger.debug(f"[{self.mind_name}] Observation: {observation['content'][:100]}...")

            session.complete()
            return session

        except Exception as e:
            logger.exception(f"[{self.mind_name}] ReAct session failed: {e}")
            session.complete()
            return session

    @abstractmethod
    async def _think(self, session: ReActSession, context: dict) -> dict:
        """Generate next thought given current state.

        Returns dict with:
            - content: the reasoning
            - type: reasoning category
            - confidence: 0-1 confidence level
            - complete: whether to stop iterating
        """
        pass

    @abstractmethod
    async def _decide_action(self, session: ReActSession, context: dict) -> dict:
        """Decide what action to take next.

        Returns dict with:
            - type: action type (search, analyze, question, propose, etc.)
            - description: what to do
            - parameters: action-specific params
        """
        pass

    @abstractmethod
    async def _execute_action(self, action: Action, context: dict) -> Any:
        """Execute the decided action and return result."""
        pass

    @abstractmethod
    async def _observe(self, result: Any, context: dict) -> dict:
        """Observe and interpret action results.

        Returns dict with:
            - content: observation summary
            - data: structured observation data
        """
        pass

    def get_session_transcript(self, session: ReActSession | None = None) -> str:
        """Get human-readable session transcript."""
        s = session or self._current_session
        if not s:
            return "No session"

        lines = [f"# {self.mind_name.upper()} ReAct Session", ""]

        for i in range(1, s.current_step):
            thought = next((t for t in s.thoughts if t.step_number == i), None)
            action = next((a for a in s.actions if a.step_number == i), None)
            obs = next((o for o in s.observations if o.step_number == i), None)

            if thought:
                lines.append(f"**Step {i}: Thought** ({thought.reasoning_type})")
                lines.append(f"{thought.content}")
                lines.append(f"_Confidence: {thought.confidence:.2f}_")
                lines.append("")

            if action:
                lines.append(f"**Action:** {action.action_type.name}")
                lines.append(f"{action.description}")
                lines.append("")

            if obs:
                lines.append(f"**Observation:**")
                lines.append(f"{obs.content}")
                lines.append("")

        return "\n".join(lines)
