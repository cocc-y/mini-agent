"""核心错误类型定义。"""


class AgentError(Exception):
    """Agent 运行时基础异常。"""


class ToolNotFoundError(AgentError):
    """工具不存在。"""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"工具 '{name}' 不存在")


class DuplicateToolError(AgentError):
    """工具重复注册。"""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"工具 '{name}' 已注册，不允许重复注册")


class ParseError(AgentError):
    """LLM 输出解析失败。"""


class LLMError(AgentError):
    """LLM API 调用失败。"""
