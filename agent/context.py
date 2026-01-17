from mcp_servers.multiMCP import MultiMCP
from typing import Optional, List
from pydantic import BaseModel
from memory.blackboard import Blackboard, BlackboardEntry, get_blackboard

class StrategyProfile(BaseModel):
    planning_mode: str
    exploration_mode: Optional[str] = None
    memory_fallback_enabled: bool
    max_steps: int
    max_lifelines_per_step: int

class AgentContext:
    def __init__(
        self,
        mcp_context: Optional[MultiMCP] = None,
        agent_name: str = "agent",
        blackboard: Optional[Blackboard] = None,
    ):

        self.mcp_context = mcp_context
        self.agent_name = agent_name
        self.blackboard = blackboard or get_blackboard()
        self._cursor = 0
        self._cache: List[BlackboardEntry] = []

    def refresh_cache(self) -> List[BlackboardEntry]:
        entries, new_cursor = self.blackboard.get_since(self._cursor)
        self._cursor = new_cursor
        self._cache.extend(entries)
        return entries

    def get_cache(self) -> List[BlackboardEntry]:
        return list(self._cache)
