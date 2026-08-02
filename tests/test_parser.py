"""LLM 输出解析逻辑测试：提取思考、工具调用、最终答案。"""

import pytest

from agent.core.errors import ParseError
from agent.core.parser import Parser


@pytest.fixture
def parser():
    return Parser()


def test_tool_call(parser):
    r = parser.parse(
        'Thought: 我需要计算一下\nAction: calculator\nAction Input: {"expression": "1+1"}'
    )
    assert r.type == "tool_call"
    assert r.thought == "我需要计算一下"
    assert r.tool_name == "calculator"
    assert r.tool_args == {"expression": "1+1"}


def test_tool_call_without_thought(parser):
    r = parser.parse('Action: calculator\nAction Input: {"expression": "2*3"}')
    assert r.type == "tool_call"
    assert r.tool_name == "calculator"
    assert r.tool_args == {"expression": "2*3"}


def test_final_answer(parser):
    r = parser.parse("Thought: 好了\nFinal Answer: 答案是 2")
    assert r.type == "final_answer"
    assert r.answer == "答案是 2"


def test_final_answer_multiline(parser):
    r = parser.parse("Thought: 好了\nFinal Answer: 第一行\n第二行\n第三行")
    assert r.type == "final_answer"
    assert r.answer == "第一行\n第二行\n第三行"


def test_final_answer_only(parser):
    r = parser.parse("Final Answer: 直接回答")
    assert r.type == "final_answer"
    assert r.answer == "直接回答"


def test_json_in_markdown_fence(parser):
    r = parser.parse(
        'Thought: x\nAction: calculator\nAction Input: ```json\n{"expression": "1+1"}\n```'
    )
    assert r.tool_args == {"expression": "1+1"}


def test_json_multiline(parser):
    r = parser.parse(
        'Thought: x\nAction: todo\nAction Input: {\n  "action": "add",\n  "item": "买牛奶"\n}'
    )
    assert r.type == "tool_call"
    assert r.tool_args == {"action": "add", "item": "买牛奶"}


def test_chinese_markers(parser):
    r = parser.parse('思考：计算\n动作：calculator\n动作输入：{"expression":"2*3"}')
    assert r.type == "tool_call"
    assert r.tool_args == {"expression": "2*3"}

    r2 = parser.parse("思考：回答\n最终答案：结果是 6")
    assert r2.type == "final_answer"
    assert r2.answer == "结果是 6"


def test_raw_text(parser):
    r = parser.parse("你好呀，今天天气不错")
    assert r.type == "raw"
    assert r.answer == "你好呀，今天天气不错"


def test_bad_json_raises(parser):
    with pytest.raises(ParseError):
        parser.parse('Thought: x\nAction: calculator\nAction Input: {broken json}')


def test_trailing_comma_json_recovered(parser):
    r = parser.parse('Thought: x\nAction: calculator\nAction Input: {"expression": "1+1", }')
    assert r.type == "tool_call"
    assert r.tool_args == {"expression": "1+1"}


def test_action_without_input_is_not_tool_call(parser):
    r = parser.parse("Thought: x\nAction: calculator\nFinal Answer: 1")
    assert r.type == "final_answer"
