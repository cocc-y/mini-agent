"""内部消息结构。

Agent 内部使用结构化的 Message 表示每一轮对话的组成部分：
用户输入、Agent 思考 + 工具调用、工具观察结果、最终答案等。
"""

from dataclasses import dataclass, field


@dataclass
class Message:
    role: str = "user"  # "user" | "assistant" | "tool"
    content: str = ""
    kind: str = "text"  # "text" | "thought" | "action" | "observation" | "final" | "error"
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"role": self.role, "kind": self.kind, "content": self.content, "meta": self.meta}

    def __repr__(self) -> str:  # pragma: no cover
        return f"Message({self.role}/{self.kind}: {self.content[:40]!r})"
