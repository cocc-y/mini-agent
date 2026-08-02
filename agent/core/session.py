"""Session 管理。

每个 Session 完全独立：拥有自己的 Context（历史 + 摘要）、
TodoStore（有状态工具数据）和 TraceLogger。
不同窗口/会话之间的对话互不影响，可随时切换回来继续聊。
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from agent.core.context import Context
from agent.core.trace import TraceLogger


def new_session_id() -> str:
    return "s-" + uuid.uuid4().hex[:8]


def default_stores() -> dict:
    # 延迟导入，避免与 tools 包形成循环导入
    from agent.tools.todo import TodoStore

    return {"todo": TodoStore()}


@dataclass
class Session:
    id: str
    context: Context
    stores: dict = field(default_factory=dict)
    trace: TraceLogger = field(default_factory=TraceLogger)
    created_at: datetime = field(default_factory=datetime.now)


class SessionManager:
    def __init__(self, context_factory=None) -> None:
        self._sessions: dict[str, Session] = {}
        self._context_factory = context_factory or (lambda: Context())

    def create(self, session_id: str = None) -> Session:
        sid = session_id or new_session_id()
        session = Session(
            id=sid,
            context=self._context_factory(),
            stores=default_stores(),
            trace=TraceLogger(),
            created_at=datetime.now(),
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            raise KeyError(f"会话 {session_id} 不存在")
        return self._sessions[session_id]

    def list(self) -> list:
        return list(self._sessions.values())

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def delete(self, session_id: str) -> None:
        if session_id not in self._sessions:
            raise KeyError(f"会话 {session_id} 不存在")
        del self._sessions[session_id]
