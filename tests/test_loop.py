"""Agent 主循环端到端测试（使用 MockLLM 驱动）。"""

from agent.core.loop import Agent
from agent.core.parser import Parser


def make_agent(registry, llm, **kwargs):
    return Agent(llm=llm, registry=registry, parser=Parser(), **kwargs)


# ---- 基础循环 ----

def test_tool_call_then_final(registry, make_session):
    llm = MockLLMResponses([
        'Thought: 需要计算 3*7\nAction: calculator\nAction Input: {"expression": "3*7"}',
        'Thought: 结果是 21\nFinal Answer: 3 乘 7 等于 21',
    ])
    agent = make_agent(registry, llm)
    s = make_session()
    result = agent.run(s, "3 乘 7 等于多少？")

    assert result.answer == "3 乘 7 等于 21"
    assert result.rounds_used == 2
    assert result.success is True
    # 第二轮请求里应包含工具观察结果 Observation: 21
    obs = [m["content"] for m in llm.calls[1] if "Observation:" in m.get("content", "")]
    assert any("21" in o for o in obs)
    # trace 记录了工具调用
    types = [e["type"] for e in result.events]
    assert "tool_call" in types and "tool_result" in types


def test_direct_reply_no_tool(registry, make_session):
    llm = MockLLMResponses(['Thought: 你好\nFinal Answer: 你好！我是 Mini Agent。'])
    agent = make_agent(registry, llm)
    s = make_session()
    result = agent.run(s, "你好")
    assert result.answer == "你好！我是 Mini Agent。"
    assert result.rounds_used == 1


def test_trace_only_contains_current_turn(registry, make_session):
    """多轮对话时，每轮返回的 trace 只包含本轮的工具调用，不再叠加历史。"""
    llm = MockLLMResponses([
        'Thought: 计算\nAction: calculator\nAction Input: {"expression": "1+1"}',
        'Thought: 结果 2\nFinal Answer: 1+1=2',
        'Thought: 计算 3*3\nAction: calculator\nAction Input: {"expression": "3*3"}',
        'Thought: 结果 9\nFinal Answer: 3*3=9',
    ])
    agent = make_agent(registry, llm)
    s = make_session()

    r1 = agent.run(s, "1+1 等于几")
    r2 = agent.run(s, "那 3*3 呢")

    # 第二轮返回的 trace 只含本轮 1 次工具调用
    tools_r2 = [e for e in r2.events if e["type"] == "tool_call"]
    assert len(tools_r2) == 1
    assert tools_r2[0]["data"]["args"] == {"expression": "3*3"}
    # 第二轮 trace 中不应出现第一轮的工具调用
    assert not any(
        e["type"] == "tool_call" and e["data"].get("args") == {"expression": "1+1"}
        for e in r2.events
    )
    # 但 Session 的完整 trace 仍保留两轮记录（供 /trace 查看）
    all_events = s.trace.snapshot()
    assert sum(1 for e in all_events if e["type"] == "tool_call") == 2


def test_raw_response_passthrough(registry, make_session):
    llm = MockLLMResponses(["直接说话，没有格式标记"])
    agent = make_agent(registry, llm)
    s = make_session()
    result = agent.run(s, "随便说点什么")
    assert result.answer == "直接说话，没有格式标记"


# ---- 追问（纯对话 + 带工具） ----

def test_pure_chat_followup(registry, make_session):
    llm = MockLLMResponses([
        'Thought: 打招呼\nFinal Answer: 你好！我是 Mini Agent。',
        'Thought: 继续聊\nFinal Answer: 我在呢，你叫小明？',
    ])
    agent = make_agent(registry, llm)
    s = make_session()
    agent.run(s, "你好")
    agent.run(s, "我叫小明")

    # 第二次请求应包含第一轮历史
    msgs = llm.calls[1]
    assert any("Mini Agent" in m.get("content", "") for m in msgs)


def test_followup_with_tool(registry, make_session):
    llm = MockLLMResponses([
        'Thought: 计算 1+1\nAction: calculator\nAction Input: {"expression": "1+1"}',
        'Thought: 结果是 2\nFinal Answer: 1+1=2',
        'Thought: 追问 2*3\nAction: calculator\nAction Input: {"expression": "2*3"}',
        'Thought: 结果是 6\nFinal Answer: 2*3=6',
    ])
    agent = make_agent(registry, llm)
    s = make_session()
    r1 = agent.run(s, "1+1 等于几")
    r2 = agent.run(s, "那 2*3 呢")

    assert r1.answer == "1+1=2"
    assert r2.answer == "2*3=6"
    # 第二轮的第一条 LLM 请求里带着第一轮的最终答案，说明状态被记住
    assert any("1+1=2" in m.get("content", "") for m in llm.calls[2])


# ---- 多工具串联（用工具结果继续） ----

def test_multi_tool_chain(registry, make_session):
    llm = MockLLMResponses([
        'Thought: 查天气\nAction: weather\nAction Input: {"city": "北京"}',
        'Thought: 查北京天气结果，再看搜索结果\nAction: search\nAction Input: {"query": "北京天气"}',
        'Thought: 综合结果\nFinal Answer: 北京今天晴，25 度。',
    ])
    agent = make_agent(registry, llm)
    s = make_session()
    result = agent.run(s, "北京天气怎么样？")
    assert result.answer == "北京今天晴，25 度。"
    assert result.rounds_used == 3
    tools_called = [e["data"].get("tool") for e in result.events if e["type"] == "tool_call"]
    assert tools_called == ["weather", "search"]


# ---- 最大轮次限制 ----

def test_max_rounds_limit(registry, make_session):
    llm = MockLLMResponses([
        'Thought: a\nAction: calculator\nAction Input: {"expression": "1+1"}',
        'Thought: b\nAction: calculator\nAction Input: {"expression": "2+2"}',
        'Thought: c\nAction: calculator\nAction Input: {"expression": "3+3"}',
    ])
    agent = make_agent(registry, llm, max_rounds=2)
    s = make_session()
    result = agent.run(s, "hi")
    assert result.rounds_used == 2
    assert result.success is False
    assert "最大轮数" in result.answer


# ---- 异常处理 ----

def test_tool_error_is_fed_back(registry, make_session):
    llm = MockLLMResponses([
        'Thought: 计算 1/0\nAction: calculator\nAction Input: {"expression": "1/0"}',
        'Thought: 出错了，我告诉用户\nFinal Answer: 表达式 1/0 无法计算',
    ])
    agent = make_agent(registry, llm)
    s = make_session()
    result = agent.run(s, "计算 1/0")
    assert result.answer == "表达式 1/0 无法计算"
    # 错误观察进入了第二轮上下文
    obs = [m["content"] for m in llm.calls[1] if "Observation:" in m.get("content", "")]
    assert any("错误" in o for o in obs)


def test_parse_error_recovery(registry, make_session):
    llm = MockLLMResponses([
        'Thought: x\nAction: calculator\nAction Input: {bad json}',
        'Thought: 修正格式\nAction: calculator\nAction Input: {"expression": "1+1"}',
        'Thought: 结果\nFinal Answer: 2',
    ])
    agent = make_agent(registry, llm)
    s = make_session()
    result = agent.run(s, "计算")
    assert result.answer == "2"
    # 解析失败的错误说明进入了第二轮上下文
    assert any("解析失败" in m.get("content", "") for m in llm.calls[1])


def test_unknown_tool_error(registry, make_session):
    llm = MockLLMResponses([
        'Thought: 调用不存在的工具\nAction: nonexist\nAction Input: {}',
        'Thought: 工具不存在，直接回答\nFinal Answer: 抱歉，我不能调用不存在的工具。',
    ])
    agent = make_agent(registry, llm)
    s = make_session()
    result = agent.run(s, "用 xx 工具")
    assert result.answer == "抱歉，我不能调用不存在的工具。"
    obs = [m["content"] for m in llm.calls[1] if "Observation:" in m.get("content", "")]
    assert any("不存在" in o for o in obs)


def test_llm_failure_returns_friendly_error(registry, make_session):
    class BoomLLM:
        def chat(self, messages, **kwargs):
            raise RuntimeError("连接超时")

    agent = make_agent(registry, BoomLLM())
    s = make_session()
    result = agent.run(s, "hi")
    assert result.success is False
    assert "LLM" in result.answer or "失败" in result.answer


# ---- Session 隔离 ----

def test_session_isolation_todos(registry, make_session):
    llm = MockLLMResponses([
        'Thought: 加待办\nAction: todo\nAction Input: {"action": "add", "item": "写周报"}',
        'Thought: 完成\nFinal Answer: 已添加待办',
        'Thought: 直接回答\nFinal Answer: 当前没有待办。',
    ])
    agent = make_agent(registry, llm)
    sa = make_session("sA")
    sb = make_session("sB")

    agent.run(sa, "帮我记住：写周报")
    agent.run(sb, "我的待办有哪些？")

    # B 的 todo 与 A 完全隔离
    assert len(sa.stores["todo"].items) == 1
    assert sb.stores["todo"].list() == "待办列表为空。"


class MockLLMResponses:
    """与 conftest.MockLLM 相同，便于测试文件内直接使用。"""

    def __init__(self, responses):
        from tests.conftest import MockLLM

        self._inner = MockLLM(responses)

    @property
    def calls(self):
        return self._inner.calls

    def chat(self, messages, **kwargs):
        return self._inner.chat(messages, **kwargs)
