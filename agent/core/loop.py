"""Agent 主循环（核心 Agent Runtime）。

流程：
  Step 1 接收用户输入
  Step 2 让 LLM 判断是直接回复，还是调用工具（输出格式约束）
  Step 3 调用工具（带异常处理）
  Step 4 根据工具结果决定继续 loop 还是返回最终答案

循环受 max_rounds 限制，避免无限迭代。
"""

import json
from dataclasses import dataclass, field

from agent.core.errors import LLMError, ParseError, ToolNotFoundError
from agent.core.message import Message
from agent.core.parser import Parser
from agent.core.tool import ToolContext, ToolRegistry


SYSTEM_PROMPT_TEMPLATE = """你是 Mini Agent，一个由零实现的 Agent Runtime 驱动的 AI 助手。

{tools}

## 输出格式

当你需要调用工具时，必须严格按以下格式输出（标记必须原样保留，可以放在 markdown 代码块中）：

Thought: <你的思考过程>
Action: <工具名>
Action Input: <符合参数 Schema 的合法 JSON 对象>

当你准备直接回答用户时，输出：

Thought: <你的思考过程>
Final Answer: <最终回答>

## 规则
- 每条回复必须以 "Thought:" 开头。
- 每轮只能调用一个工具。
- Action Input 必须是合法 JSON，参数必须匹配对应工具的 Schema。
- 只能使用上面列出的工具，不要编造工具名。
- 使用与用户相同的语言回答。
- 如果工具执行出错或信息不足，可以继续调用工具，也可以基于已有信息回答。
- 回答要简洁、直接。"""


def build_system_prompt(registry: ToolRegistry) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(tools=registry.system_prompt())


@dataclass
class AgentResult:
    session_id: str
    answer: str
    rounds_used: int
    events: list = field(default_factory=list)
    success: bool = True


class Agent:
    def __init__(
        self,
        llm,
        registry: ToolRegistry,
        parser: Parser = None,
        *,
        max_rounds: int = 6,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.parser = parser or Parser()
        self.max_rounds = max_rounds

    # ---- 公共入口 ----

    def run(self, session, user_input: str) -> AgentResult:
        ctx = session.context
        trace = session.trace
        # 记录本轮开始前的事件数，返回结果时只包含本轮新增的 trace
        trace_start = len(trace.events)

        ctx.start_turn(user_input)
        trace.log("user_input", user_input)
        system_prompt = build_system_prompt(self.registry)

        rounds = 0
        while rounds < self.max_rounds:
            rounds += 1
            messages = ctx.build_llm_messages(system_prompt)
            trace.log("llm_request", {"round": rounds, "message_count": len(messages)})

            try:
                response = self.llm.chat(messages)
            except Exception as e:  # noqa: BLE001
                trace.log("llm_error", str(e), level="error")
                ctx.end_turn()
                return AgentResult(
                    session.id, f"调用 LLM 失败：{e}", rounds, trace.since(trace_start), success=False
                )

            if not response or not response.strip():
                trace.log("llm_error", "LLM 返回空响应", level="error")
                ctx.end_turn()
                return AgentResult(
                    session.id, "LLM 返回了空响应，请重试。", rounds, trace.since(trace_start), success=False
                )

            trace.log("llm_response", {"round": rounds, "content": response})

            try:
                parsed = self.parser.parse(response)
            except ParseError as e:
                # 解析失败：把错误作为观察喂回 LLM，让它重新输出
                trace.log("parse_error", str(e), level="warn")
                ctx.add(Message(role="assistant", content=response, kind="raw"))
                ctx.add(
                    Message(
                        role="tool",
                        content=f"输出解析失败：{e}。请严格按照格式重新输出 Action 和 Action Input（合法 JSON）。",
                        kind="error",
                    )
                )
                continue

            if parsed.type == "tool_call":
                self._handle_tool_call(session, ctx, trace, parsed)
                continue

            if parsed.type == "final_answer":
                final_text = (
                    f"Thought: {parsed.thought}\nFinal Answer: {parsed.answer}"
                    if parsed.thought
                    else f"Final Answer: {parsed.answer}"
                )
                ctx.add(Message(role="assistant", content=final_text, kind="final"))
                ctx.end_turn()
                trace.log("final_answer", parsed.answer)
                return AgentResult(session.id, parsed.answer, rounds, trace.since(trace_start))

            # raw：直接把 LLM 原文当作答案返回
            ctx.add(Message(role="assistant", content=response, kind="final"))
            ctx.end_turn()
            trace.log("final_answer_raw", response)
            return AgentResult(session.id, response, rounds, trace.since(trace_start))

        # 达到最大轮数
        closing = Message(
            role="assistant",
            content=f"已达到最大工具调用轮数（{self.max_rounds}），基于已有信息结束本轮。",
            kind="final",
        )
        ctx.add(closing)
        ctx.end_turn()
        trace.log("max_rounds_exceeded", {"max_rounds": self.max_rounds}, level="warn")
        return AgentResult(
            session.id,
            "抱歉，我在达到最大轮数后仍未得到最终答案，请换个问法或重试。",
            rounds,
            trace.since(trace_start),
            success=False,
        )

    # ---- 工具调用分支 ----

    def _handle_tool_call(self, session, ctx, trace, parsed) -> None:
        action_text = (
            f"Thought: {parsed.thought}\n"
            f"Action: {parsed.tool_name}\n"
            f"Action Input: {json.dumps(parsed.tool_args, ensure_ascii=False)}"
        )
        ctx.add(
            Message(
                role="assistant",
                content=action_text,
                kind="action",
                meta={"tool_name": parsed.tool_name, "tool_args": parsed.tool_args},
            )
        )
        tool_ctx = ToolContext(session_id=session.id, stores=session.stores)
        trace.log("tool_call", {"tool": parsed.tool_name, "args": parsed.tool_args})

        try:
            result = self.registry.run(parsed.tool_name, parsed.tool_args, tool_ctx)
            trace.log("tool_result", {"tool": parsed.tool_name, "result": result})
        except ToolNotFoundError as e:
            result = f"错误：工具“{parsed.tool_name}”不存在。可用工具：{', '.join(self.registry.names())}"
            trace.log("tool_error", str(e), level="error")
        except Exception as e:  # noqa: BLE001
            result = f"错误：工具执行失败 - {e}"
            trace.log("tool_error", str(e), level="error")

        ctx.add(Message(role="tool", content=result, kind="observation"))
