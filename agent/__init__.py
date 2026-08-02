"""Mini Agent — 从零实现的最小可用 Agent Runtime。

不依赖任何现有 Agent 框架（langgraph/openhands/openclaw），
核心的 LLM 输出解析、工具注册、Agent 循环、上下文与 Session 管理全部自行实现。
"""

__version__ = "0.1.0"

from agent.core.errors import (
    AgentError,
    ToolNotFoundError,
    DuplicateToolError,
    ParseError,
    LLMError,
)
from agent.core.tool import Tool, ToolContext, ToolRegistry
from agent.core.message import Message
from agent.core.context import Context, HistoryCompressor
from agent.core.session import Session, SessionManager
from agent.core.parser import Parser, ParseResult
from agent.core.loop import Agent, AgentResult
from agent.core.llm import LLMClient
from agent.core.config import AgentConfig, config_from_env, load_env

__all__ = [
    "AgentError",
    "ToolNotFoundError",
    "DuplicateToolError",
    "ParseError",
    "LLMError",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "Message",
    "Context",
    "HistoryCompressor",
    "Session",
    "SessionManager",
    "Parser",
    "ParseResult",
    "Agent",
    "AgentResult",
    "LLMClient",
    "AgentConfig",
    "config_from_env",
    "load_env",
]
