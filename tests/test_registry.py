"""工具注册机制测试。"""

import pytest

from agent.core.errors import DuplicateToolError, ToolNotFoundError
from agent.core.tool import ToolRegistry
from agent.tools.calculator import CalculatorTool


def test_registered_tools(registry):
    assert set(registry.names()) == {"calculator", "search", "todo", "weather"}
    assert "calculator" in registry
    assert "nope" not in registry


def test_duplicate_registration_rejected(registry):
    with pytest.raises(DuplicateToolError):
        registry.register(CalculatorTool())


def test_run_unknown_tool(registry):
    with pytest.raises(ToolNotFoundError):
        registry.run("不存在的工具", {})


def test_required_parameter_validation(registry):
    # calculator 的 expression 是必填参数
    with pytest.raises(ValueError, match="expression"):
        registry.run("calculator", {})


def test_system_prompt_contains_schema(registry):
    prompt = registry.system_prompt()
    assert "calculator" in prompt
    assert "expression" in prompt
    assert '"type": "object"' in prompt
