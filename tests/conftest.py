"""pytest 全局配置与共享夹具。"""

import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.core.context import Context
from agent.core.session import Session
from agent.core.trace import TraceLogger
from agent.core.tool import ToolRegistry
from agent.tools.calculator import CalculatorTool
from agent.tools.search import SearchTool
from agent.tools.todo import TodoStore, TodoTool
from agent.tools.weather import WeatherTool


class MockLLM:
    """按脚本顺序返回预设回复的 LLM 替身，并记录每次请求。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(list(messages))
        if not self.responses:
            raise AssertionError(
                f"MockLLM 没有更多预设响应，第 {len(self.calls)} 次调用，"
                f"收到的消息:\n{messages}"
            )
        return self.responses.pop(0)


@pytest.fixture
def registry():
    # 测试统一使用 mock 后端，保证确定性、不依赖网络
    reg = ToolRegistry()
    reg.register_many(
        [
            CalculatorTool(),
            SearchTool(backend="mock"),
            TodoTool(),
            WeatherTool(backend="mock"),
        ]
    )
    return reg


@pytest.fixture
def make_session():
    def _make(sid="s-test"):
        ctx = Context(max_history_messages=16)
        return Session(
            id=sid,
            context=ctx,
            stores={"todo": TodoStore()},
            trace=TraceLogger(),
            created_at=datetime.now(),
        )

    return _make
