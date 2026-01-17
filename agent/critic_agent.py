from __future__ import annotations

from memory.blackboard import post_to_blackboard
from agent.context import AgentContext


class CriticAgent:
    def __init__(self, agent_name: str = "special-critic") -> None:
        self.agent_name = agent_name

    def critique(self, perception_result: dict, context: AgentContext) -> None:
        confidence = perception_result.get("confidence", "0.0")
        message = (
            "Low confidence detected. Recommend clarifying inputs, "
            "validating tool outputs, and tightening the plan steps."
        )
        post_to_blackboard(self.agent_name, f"confidence={confidence}; {message}")
