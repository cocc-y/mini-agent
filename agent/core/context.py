"""上下文管理器。

职责：
1. 组织发给 LLM 的 messages（system + 摘要 + 历史轮次 + 当前轮）
2. 维护「当前轮」的思考 / 动作 / 观察消息
3. 轮次结束时归档到历史，并在历史过长时做基础压缩
4. 限制最大历史条数（max_history_messages）

放进 context 的信息：
  - 用户输入（user text）
  - Agent 思考 + 工具调用（assistant action）
  - 工具执行结果（observation）
  - 最终答案（assistant final）
历史中保留完整轮次，支撑纯对话追问与「带工具的追问」。
"""

from agent.core.message import Message


class HistoryCompressor:
    """基础压缩器。

    优先使用 LLM 生成摘要；LLM 不可用时退化为「抽取式压缩」：
    只保留用户输入、工具结果与最终答案，并截断长度。
    """

    def __init__(self, llm=None, max_chars: int = 800) -> None:
        self.llm = llm
        self.max_chars = max_chars

    def compress(self, turns: list) -> str:
        if self.llm is not None:
            try:
                text = self._render_turns(turns)[:3000]
                prompt = (
                    "请把下面这段 Agent 对话压缩成一段简短的中文摘要，"
                    "保留用户意图、工具调用结果和结论。只输出摘要本身：\n\n"
                    f"{text}\n\n摘要："
                )
                result = self.llm.chat([{"role": "user", "content": prompt}])
                if result and result.strip():
                    return result.strip()[: self.max_chars]
            except Exception:  # noqa: BLE001
                pass
        return self._fallback(turns)

    def _render_turns(self, turns) -> str:
        parts = []
        for turn in turns:
            for m in turn:
                if m.role == "user":
                    parts.append(f"用户: {m.content}")
                elif m.role == "tool":
                    parts.append(f"工具: {m.content}")
                elif m.kind == "final":
                    parts.append(f"Agent: {m.content}")
        return "\n".join(parts)

    def _fallback(self, turns) -> str:
        parts = []
        for turn in turns:
            user_msgs = [m for m in turn if m.role == "user"]
            obs = [m for m in turn if m.role == "tool"]
            finals = [m for m in turn if m.kind == "final"]
            if user_msgs:
                parts.append("用户: " + user_msgs[0].content)
            if obs:
                parts.append("工具: " + " | ".join(o.content for o in obs)[:200])
            if finals:
                parts.append("Agent: " + finals[0].content[:200])
        text = " || ".join(parts)
        if len(text) > self.max_chars:
            text = text[: self.max_chars] + "..."
        return text


class Context:
    def __init__(self, max_history_messages: int = 16, compressor: HistoryCompressor = None) -> None:
        self.max_history_messages = max_history_messages
        self.compressor = compressor or HistoryCompressor()
        self.summary: str = ""          # 被压缩掉的历史的摘要（背景记忆）
        self.history: list = []         # 已完成轮次（每轮是一组 Message）
        self.current: list = []         # 当前轮的 Message

    # ---- 轮次管理 ----

    def start_turn(self, user_input: str) -> None:
        self.current = [Message(role="user", content=user_input, kind="text")]

    def add(self, msg: Message) -> None:
        self.current.append(msg)

    def end_turn(self) -> None:
        if self.current:
            self.history.append(self.current)
            self.current = []
        self._maybe_compress()

    # ---- 压缩 ----

    def _maybe_compress(self) -> None:
        count = sum(len(turn) for turn in self.history)
        while count > self.max_history_messages and len(self.history) > 1:
            removed = self.history.pop(0)
            count -= len(removed)
            self._absorb(removed)

    def _absorb(self, turn: list) -> None:
        try:
            summary = self.compressor.compress([turn])
        except Exception:  # noqa: BLE001
            summary = ""
        if summary:
            self.summary = (self.summary + "\n" + summary).strip() if self.summary else summary
            if len(self.summary) > 1200:  # 摘要本身也要限长
                self.summary = self.summary[-1200:]

    # ---- 组装 LLM 消息 ----

    def build_llm_messages(self, system_prompt: str) -> list:
        msgs = [{"role": "system", "content": system_prompt}]
        if self.summary:
            msgs.append(
                {
                    "role": "system",
                    "content": "以下是更早对话的压缩摘要（背景记忆）：\n" + self.summary,
                }
            )
        for turn in self.history:
            for m in turn:
                msgs.append(self._to_api(m))
        for m in self.current:
            msgs.append(self._to_api(m))
        return msgs

    def _to_api(self, m: Message) -> dict:
        if m.role == "tool":
            # 文本式 ReAct：工具观察结果以 user 消息 + Observation 前缀返回
            return {"role": "user", "content": "Observation: " + m.content}
        if m.role == "assistant":
            return {"role": "assistant", "content": m.content}
        return {"role": "user", "content": m.content}

    def stats(self) -> dict:
        return {
            "history_turns": len(self.history),
            "current_messages": len(self.current),
            "summary_len": len(self.summary),
        }
