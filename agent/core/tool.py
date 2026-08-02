"""工具框架：Tool 基类、ToolContext、ToolRegistry。

- 每个工具包含：名称、描述、参数 JSON Schema
- LLM 基于 Schema 自主决策调用
- ToolRegistry 提供注册 / 查询 / 执行 / 生成系统提示词
"""

import json

from agent.core.errors import DuplicateToolError, ToolNotFoundError


class Tool:
    name: str = ""
    description: str = ""
    parameters: dict = {}

    def run(self, args: dict, ctx: "ToolContext") -> str:
        raise NotImplementedError(f"工具 {self.name} 未实现 run()")


class ToolContext:
    """工具执行上下文，携带 session 维度的状态（如待办存储）。"""

    def __init__(self, session_id: str = "", stores: dict = None) -> None:
        self.session_id = session_id
        self.stores = stores or {}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise DuplicateToolError("<empty>")
        if tool.name in self._tools:
            raise DuplicateToolError(tool.name)
        self._tools[tool.name] = tool

    def register_many(self, tools) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str):
        return self._tools.get(name)

    def names(self) -> list:
        return list(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def run(self, name: str, args: dict, ctx: ToolContext = None) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        self._validate(tool, args or {})
        return tool.run(args or {}, ctx or ToolContext())

    def _validate(self, tool: Tool, args: dict) -> None:
        schema = tool.parameters or {}
        required = schema.get("required", [])
        missing = [k for k in required if k not in args]
        if missing:
            raise ValueError(f"缺少必需参数: {missing}")

    def system_prompt(self) -> str:
        """把全部工具渲染成 LLM 可见的描述 + 参数 Schema。"""
        lines = ["你可以使用以下工具：", ""]
        for tool in self._tools.values():
            lines.append(f"### {tool.name}")
            lines.append(tool.description)
            lines.append(
                f"参数 Schema: {json.dumps(tool.parameters, ensure_ascii=False)}"
            )
            lines.append("")
        return "\n".join(lines).strip()
