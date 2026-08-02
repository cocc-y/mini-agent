"""内置工具：安全计算器。

基于 AST 白名单求值，杜绝代码注入（不执行任意 Python）。
"""

import ast
import math
import operator

from agent.core.tool import Tool

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculatorTool(Tool):
    name = "calculator"
    description = (
        "计算数学表达式，支持 + - * / // % ** 和括号，以及常量 pi、e 和函数 sqrt()。"
        "例如：3.5 * (2 + 4) / 7"
    )
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "要计算的数学表达式，例如 3.5 * (2 + 4) / 7",
            }
        },
        "required": ["expression"],
    }

    def run(self, args: dict, ctx) -> str:
        expr = str(args.get("expression", "")).strip()
        if not expr:
            return "错误：缺少 expression 参数"
        try:
            tree = ast.parse(expr, mode="eval")
            value = self._eval(tree.body)
        except Exception as e:  # noqa: BLE001
            return f"错误：计算失败 - {e}"
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return f"{value:.10g}"
        return str(value)

    def _eval(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"不支持的常量: {node.value!r}")
        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
            return op(self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
            return op(self._eval(node.operand))
        if isinstance(node, ast.Name):
            if node.id == "pi":
                return math.pi
            if node.id == "e":
                return math.e
            raise ValueError(f"不支持的变量: {node.id}")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "sqrt" and len(node.args) == 1:
                return math.sqrt(self._eval(node.args[0]))
            raise ValueError("只支持 sqrt() 函数")
        raise ValueError(f"不支持的表达式节点: {type(node).__name__}")
