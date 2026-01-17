from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple


@dataclass
class BlackboardEntry:
    timestamp: str
    agent_name: str
    message: str


class Blackboard:
    def __init__(self) -> None:
        self._entries: List[BlackboardEntry] = []

    def post(self, agent_name: str, message: str) -> BlackboardEntry:
        entry = BlackboardEntry(
            timestamp=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            agent_name=agent_name,
            message=message,
        )
        self._entries.append(entry)
        return entry

    def get_since(self, cursor: int) -> Tuple[List[BlackboardEntry], int]:
        if cursor < 0:
            cursor = 0
        entries = self._entries[cursor:]
        return entries, len(self._entries)


_BLACKBOARD = Blackboard()


def post_to_blackboard(agent_name: str, message: str) -> BlackboardEntry:
    """Standardized trace entry for agents."""
    return _BLACKBOARD.post(agent_name, message)


def get_blackboard() -> Blackboard:
    return _BLACKBOARD
