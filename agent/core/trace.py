"""工具调用 / 执行的 Trace 日志。

每一条事件包含时间戳、类型、级别和数据，可渲染成文本供用户查看，
满足「工具调用 trace 或执行日志」的要求。
"""

from datetime import datetime
from typing import Any, List


class TraceLogger:
    """按 session 维护一条事件流水线。"""

    def __init__(self) -> None:
        self.events: List[dict] = []

    def log(self, event_type: str, data: Any, level: str = "info") -> None:
        self.events.append(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "type": event_type,
                "level": level,
                "data": data,
            }
        )

    def snapshot(self) -> List[dict]:
        return list(self.events)

    def since(self, index: int) -> List[dict]:
        """返回从 index（含）开始的事件，用于只取「当前这一轮」的 trace。"""
        return self.events[index:]

    def to_text(self) -> str:
        lines = []
        for e in self.events:
            lines.append(f"[{e['ts']}] [{e['level'].upper()}] {e['type']}: {e['data']}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.events)
