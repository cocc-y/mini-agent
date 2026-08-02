"""命令行交互入口。

支持多 Session 管理：/new /list /switch /delete，以及 /trace /stats 调试命令。
运行：python -m agent.cli
"""

import sys

# Windows 控制台默认可能是 GBK 编码，统一输出为 UTF-8 避免中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from agent.core.config import config_from_env, load_env
from agent.core.context import Context
from agent.core.llm import LLMClient
from agent.core.loop import Agent
from agent.core.parser import Parser
from agent.core.session import SessionManager
from agent.core.tool import ToolRegistry
from agent.tools import DEFAULT_TOOLS

BANNER = r"""
 __  __ _       _        ___   _   _
|  \/  (_)_ __ (_) ___  | __|_(_)_ __ ___  ___ ___
| |\/| | | '_ \| |/ _ \ | _|\ \| | '_ \ / _ \/ -_|-_/
|_|  |_|_| .__/|_|\___/ |___/_\_\_| .__/\___/\___/__/
         |_|                      |_|
从零实现的最小可用 Agent Runtime  v0.1
"""

HELP = """命令：
  /help            显示帮助
  /new             创建并切换到新会话（新窗口）
  /list            列出所有会话
  /switch <id>     切换到指定会话
  /delete <id>     删除指定会话
  /trace           打印当前会话的完整执行 Trace
  /stats           打印当前会话的上下文统计
  /quit            退出
直接输入文本即可与 Agent 对话。"""


def show_compact_trace(events: list) -> None:
    """每轮回复后打印精简易读的 trace（只列工具调用与错误）。"""
    print("  -- trace --")
    for e in events:
        t, d = e["type"], e["data"]
        if t == "tool_call":
            print(f"   [工具调用] {d.get('tool')}  参数: {d.get('args')}")
        elif t == "tool_error":
            print(f"   [工具错误] {d}")
        elif t == "parse_error":
            print(f"   [解析错误] {d}")
        elif t == "llm_error":
            print(f"   [LLM错误] {d}")
        elif t == "max_rounds_exceeded":
            print(f"   [已达最大轮数] {d}")
    print()


def handle_command(line: str, sm: SessionManager, session) -> object:
    parts = line.split()
    cmd = parts[0]
    if cmd == "/help":
        print(HELP)
    elif cmd == "/new":
        session = sm.create()
        print(f"已创建并切换到新会话：{session.id}")
    elif cmd == "/list":
        if not sm.list():
            print("当前没有任何会话。")
        for s in sm.list():
            n = sum(len(t) for t in s.context.history)
            print(f"  {s.id}  (创建于 {s.created_at:%H:%M:%S}, 历史消息 {n} 条)")
    elif cmd == "/switch":
        sid = parts[1] if len(parts) > 1 else ""
        try:
            session = sm.get(sid)
            print(f"已切换到会话：{sid}")
        except KeyError as e:
            print(f"[错误] {e}")
    elif cmd == "/delete":
        sid = parts[1] if len(parts) > 1 else ""
        try:
            sm.delete(sid)
            print(f"已删除会话：{sid}")
            if session.id == sid:
                session = sm.create()
                print(f"已创建新会话：{session.id}")
        except KeyError as e:
            print(f"[错误] {e}")
    elif cmd == "/trace":
        print(session.trace.to_text())
    elif cmd == "/stats":
        print(session.context.stats())
    else:
        print("未知命令，输入 /help 查看。")
    return session


def main() -> None:
    load_env()
    cfg = config_from_env()
    if not cfg.api_key:
        print("[错误] 未配置 LLM_API_KEY。请在 .env 中填写，或设置环境变量 LLM_API_KEY。")
        print("参考 .env.example；不同模型厂商的 base_url / model 配置见 README。")
        sys.exit(1)

    registry = ToolRegistry()
    registry.register_many(DEFAULT_TOOLS)
    llm = LLMClient(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        model=cfg.model,
        temperature=cfg.temperature,
        timeout=cfg.timeout,
    )
    agent = Agent(
        llm=llm,
        registry=registry,
        parser=Parser(),
        max_rounds=cfg.max_rounds,
    )
    sm = SessionManager(
        context_factory=lambda: Context(max_history_messages=cfg.max_history_messages)
    )
    session = sm.create()

    print(BANNER)
    print(f"模型: {cfg.model}  |  接口: {cfg.base_url}")
    print("输入 /help 查看命令。当前会话：" + session.id + "\n")

    while True:
        try:
            line = input(f"[{session.id}] 你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not line:
            continue
        if line.startswith("/"):
            session = handle_command(line, sm, session)
            continue

        try:
            result = agent.run(session, line)
        except Exception as e:  # noqa: BLE001
            print(f"[系统错误] {e}")
            continue
        print(f"\nAgent > {result.answer}\n")
        show_compact_trace(result.events)


if __name__ == "__main__":
    main()
