from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock


@dataclass(slots=True)
class ConversationTurn:
    role: str
    content: str


class MemoryService:
    def __init__(self, max_turns: int = 6) -> None:
        self.max_turns = max_turns
        self._sessions: dict[str, deque[ConversationTurn]] = defaultdict(lambda: deque(maxlen=max_turns))
        self._lock = Lock()

    def append_turn(self, session_id: str, role: str, content: str) -> None:
        if not session_id or not content.strip():
            return
        with self._lock:
            self._sessions[session_id].append(ConversationTurn(role=role, content=content.strip()))

    def recent_turns(self, session_id: str, limit: int = 4) -> list[ConversationTurn]:
        if not session_id:
            return []
        with self._lock:
            turns = list(self._sessions.get(session_id, ()))
        return turns[-limit:]

    def format_context(self, session_id: str, limit: int = 4) -> str:
        turns = self.recent_turns(session_id, limit=limit)
        if not turns:
            return ""
        lines = ["Recent conversation:"]
        for turn in turns:
            speaker = "User" if turn.role == "user" else "Assistant"
            lines.append(f"- {speaker}: {turn.content}")
        return "\n".join(lines)

    def reset(self, session_id: str) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)
