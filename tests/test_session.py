"""Session 管理测试：创建 / 查询 / 删除 / 隔离。"""

import pytest

from agent.core.message import Message
from agent.core.session import SessionManager


def test_create_get_list_delete():
    sm = SessionManager()
    a = sm.create()
    b = sm.create()
    assert a.id != b.id
    assert sm.get(a.id) is a
    assert len(sm.list()) == 2
    assert sm.exists(a.id)

    sm.delete(a.id)
    assert not sm.exists(a.id)
    assert len(sm.list()) == 1
    with pytest.raises(KeyError):
        sm.get(a.id)
    with pytest.raises(KeyError):
        sm.delete(a.id)


def test_sessions_are_isolated():
    sm = SessionManager()
    a = sm.create()
    b = sm.create()

    a.context.start_turn("hello")
    a.context.add(Message(role="assistant", content="Final Answer: hi", kind="final"))
    a.context.end_turn()

    # A 的历史不会出现在 B
    assert len(b.context.history) == 0
    assert len(a.context.history) == 1
    # 各自的 todo 存储独立
    a.stores["todo"].add("写周报")
    assert b.stores["todo"].list() == "待办列表为空。"


def test_switch_back_and_continue():
    sm = SessionManager()
    a = sm.create()
    b = sm.create()
    a.context.start_turn("记住：项目周五截止")
    a.context.add(Message(role="assistant", content="Final Answer: 好的", kind="final"))
    a.context.end_turn()

    # 切回 A，历史还在
    again = sm.get(a.id)
    assert again is a
    msgs = again.context.build_llm_messages("SYSTEM")
    assert any("项目周五截止" in m["content"] for m in msgs)
