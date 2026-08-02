"""LLM 输出解析器。

把 LLM 的文本输出解析为三类结构：
  - tool_call    思考 + 工具名 + 参数（Action / Action Input）
  - final_answer 思考 + 最终答案（Final Answer）
  - raw          既没有 Action 也没有 Final Answer 的裸文本

同时兼容中英文标记（思考/动作/动作输入/最终答案），并处理 JSON 代码块围栏。
"""

import json
import re
from dataclasses import dataclass, field

from agent.core.errors import ParseError


@dataclass
class ParseResult:
    type: str = "raw"  # "tool_call" | "final_answer" | "raw"
    thought: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    answer: str = ""
    raw: str = ""


class Parser:
    def parse(self, text: str) -> ParseResult:
        if text is None:
            text = ""
        text = text.strip()
        if not text:
            return ParseResult(type="raw", raw=text)

        # 去掉 markdown 代码块围栏
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        text = self._normalize_markers(text)
        raw = text

        has_action = re.search(r"(?im)^\s*Action\s*:", text)
        has_action_input = re.search(r"(?im)^\s*Action\s+Input\s*:", text)
        has_final = re.search(r"(?im)^\s*Final\s+Answer\s*:", text)

        if has_action and has_action_input:
            thought = self._extract_thought(text)
            tool_name = self._line_value_after(text, "Action:")
            input_section = self._value_after(text, "Action Input:")
            # 截断到下一个 Thought（防止一次回复里出现多步）
            input_section = re.split(r"(?im)^\s*Thought\s*:", input_section)[0]
            args = self._parse_json(input_section)
            return ParseResult(
                type="tool_call",
                thought=thought,
                tool_name=tool_name,
                tool_args=args,
                raw=raw,
            )

        if has_final:
            thought = self._extract_thought(text)
            answer = self._value_after(text, "Final Answer:")
            return ParseResult(
                type="final_answer", thought=thought, answer=answer, raw=raw
            )

        return ParseResult(type="raw", answer=text, raw=raw)

    # ---- 内部工具方法 ----

    def _normalize_markers(self, text: str) -> str:
        repl = [
            ("动作输入：", "Action Input:"),
            ("动作输入:", "Action Input:"),
            ("动作：", "Action:"),
            ("动作:", "Action:"),
            ("最终回答：", "Final Answer:"),
            ("最终回答:", "Final Answer:"),
            ("最终答案：", "Final Answer:"),
            ("最终答案:", "Final Answer:"),
            ("思考：", "Thought:"),
            ("思考:", "Thought:"),
        ]
        for old, new in repl:
            text = text.replace(old, new)
        return text

    def _extract_thought(self, text: str) -> str:
        m = re.search(
            r"(?is)^\s*Thought\s*:\s*(.*?)(?=\n\s*(?:Action\s*:|Action\s+Input\s*:|Final\s+Answer\s*:))",
            text,
        )
        return m.group(1).strip() if m else ""

    def _value_after(self, text: str, marker: str) -> str:
        # marker 形如 "Action Input:"（自带冒号），返回冒号之后的所有内容
        m = re.search(rf"(?im)^\s*{re.escape(marker)}", text)
        if not m:
            return ""
        return text[m.end():].strip()

    def _line_value_after(self, text: str, marker: str) -> str:
        # 只取同一行冒号之后的内容（用于工具名等单行字段）
        m = re.search(rf"(?im)^\s*{re.escape(marker)}\s*(.*)$", text)
        return m.group(1).strip() if m else ""

    def _parse_json(self, section: str) -> dict:
        obj = self._extract_balanced_json(section)
        if obj is None:
            raise ParseError(f"Action Input 中未找到 JSON 对象: {section[:80]!r}")
        try:
            parsed = json.loads(obj)
            if not isinstance(parsed, dict):
                raise ParseError(f"Action Input 必须是 JSON 对象，得到: {obj[:120]!r}")
            return parsed
        except json.JSONDecodeError:
            fixed = self._try_fix_json(obj)
            if fixed is not None:
                return fixed
            raise ParseError(f"Action Input 不是合法 JSON: {obj[:120]!r}")

    @staticmethod
    def _extract_balanced_json(s: str):
        """在字符串中抽取第一个平衡的 {} 对象。"""
        start = s.find("{")
        if start == -1:
            return None
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]
        return None

    @staticmethod
    def _try_fix_json(s: str):
        """常见错误修复：去掉尾随逗号、把单引号替换为双引号。"""
        s2 = re.sub(r",(\s*[}\]])", r"\1", s)
        s2 = s2.replace("'", '"')
        try:
            return json.loads(s2)
        except Exception:  # noqa: BLE001
            return None
