"""上下文管理测试：历史组装、压缩、追问支持。"""

from agent.core.context import Context, HistoryCompressor
from agent.core.message import Message


def test_history_is_remembered_for_followup():
    ctx = Context(max_history_messages=16)
    ctx.start_turn("你好")
    ctx.add(Message(role="assistant", content="Thought: 打招呼\nFinal Answer: 你好！", kind="final"))
    ctx.end_turn()

    ctx.start_turn("帮我算 1+1")
    msgs = ctx.build_llm_messages("SYSTEM")
    assert msgs[0] == {"role": "system", "content": "SYSTEM"}
    contents = [m["content"] for m in msgs]
    # 上一轮的用户输入与最终答案都进入了本轮上下文
    assert "你好" in contents
    assert any("Final Answer: 你好！" in m for m in contents)
    assert "帮我算 1+1" in contents


def test_tool_observation_mapped_to_user_role():
    ctx = Context(max_history_messages=16)
    ctx.start_turn("计算")
    ctx.add(Message(role="assistant", content="Thought: a\nAction: calculator\nAction Input: {}", kind="action"))
    ctx.add(Message(role="tool", content="21", kind="observation"))
    msgs = ctx.build_llm_messages("SYSTEM")
    api_msg = msgs[-1]
    assert api_msg["role"] == "user"
    assert api_msg["content"] == "Observation: 21"


def test_compression_triggers_when_history_long():
    ctx = Context(max_history_messages=4)  # 每轮 2 条消息，4 条 = 2 轮
    for i in range(6):
        ctx.start_turn(f"问题{i}")
        ctx.add(Message(role="assistant", content=f"Thought: t\nFinal Answer: 回答{i}", kind="final"))
        ctx.end_turn()

    assert ctx.summary != ""  # 最早几轮被压缩进摘要
    total = sum(len(t) for t in ctx.history)
    assert total <= 4
    assert len(ctx.history) >= 1

    # 摘要作为 system 消息放进下一轮上下文
    msgs = ctx.build_llm_messages("SYSTEM")
    assert any("摘要" in m["content"] for m in msgs if m["role"] == "system")


def test_compressor_fallback_keeps_key_info():
    comp = HistoryCompressor()  # 无 llm，走抽取式压缩
    turns = [
        [
            Message(role="user", content="帮我记待办：买牛奶", kind="text"),
            Message(role="assistant", content="Thought: x\nAction: todo\nAction Input: {}", kind="action"),
            Message(role="tool", content="已添加待办：买牛奶", kind="observation"),
            Message(role="assistant", content="Thought: y\nFinal Answer: 已添加", kind="final"),
        ]
    ]
    summary = comp.compress(turns)
    assert "买牛奶" in summary
    assert "已添加" in summary


def test_empty_turn_noop():
    ctx = Context(max_history_messages=4)
    ctx.end_turn()
    assert ctx.history == []


def test_stats():
    ctx = Context(max_history_messages=16)
    ctx.start_turn("hi")
    st = ctx.stats()
    assert st["current_messages"] == 1
