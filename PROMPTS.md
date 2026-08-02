# AI Prompt 与问题解决记录

本文记录 Mini Agent 开发过程中使用的关键 Prompt（System Prompt / 压缩 Prompt），
以及在开发中遇到并解决的问题。

## 一、Agent System Prompt（发给真实 LLM）

该 Prompt 让 LLM 基于工具 Schema 自主决策调用工具，并输出可解析的结构化文本。
位置：`agent/core/loop.py` 中的 `SYSTEM_PROMPT_TEMPLATE`。

```
你是 Mini Agent，一个由零实现的 Agent Runtime 驱动的 AI 助手。

你可以使用以下工具：

### calculator
计算数学表达式，支持 + - * / // % ** 和括号，以及常量 pi、e 和函数 sqrt()。例如：3.5 * (2 + 4) / 7
参数 Schema: {"type": "object", "properties": {"expression": {"type": "string", "description": "要计算的数学表达式，例如 3.5 * (2 + 4) / 7"}}, "required": ["expression"]}

### search
搜索信息（mock 实现）。根据关键词返回本地知识库中的相关条目。
参数 Schema: {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}}, "required": ["query"]}

### todo
管理待办事项。action 支持 add(添加)、list(列出)、done(标记完成)、remove(删除)。
参数 Schema: {"type": "object", "properties": {...}, "required": ["action"]}

### weather
查询天气（mock 实现）。输入城市名返回模拟天气。
参数 Schema: {"type": "object", "properties": {"city": {"type": "string", "description": "城市名称，例如 北京"}}, "required": ["city"]}

## 输出格式

当你需要调用工具时，必须严格按以下格式输出：

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
- 回答要简洁、直接。
```

### 设计要点

- **结构化文本而非 function calling**：为了满足“需实现 LLM 输出的解析逻辑，提取思考过程、
  工具调用或最终答案”这一要求，采用 ReAct 风格的文本格式，由自己写解析器，而不是用
  厂商的 function calling 能力。
- **工具 Schema 进 System Prompt**：让 LLM“看到”每个工具的参数约束，实现基于 Schema 的自主决策。
- **单轮单工具**：每轮只允许一个 Action，简化解析与循环；多次调用通过多轮迭代实现。

## 二、上下文压缩 Prompt（历史过长时触发）

位置：`agent/core/context.py` 中的 `HistoryCompressor.compress`。

```
请把下面这段 Agent 对话压缩成一段简短的中文摘要，
保留用户意图、工具调用结果和结论。只输出摘要本身：

<更早的对话轮次>

摘要：
```

失败时退化为“抽取式压缩”：只拼出 用户输入 / 工具结果 / 最终答案 并限长。

## 三、开发中遇到的问题与解决记录

### 问题 1：解析器取“工具名”时把后续内容全吞掉
- **现象**：`Action: calculator\nAction Input: {...}` 解析出 `tool_name` 变成了
  `calculator\nAction Input: {...}`。
- **原因**：`_value_after` 返回冒号之后的**全部内容**，工具名却是“同一行内”的字段。
- **解决**：新增 `_line_value_after`（只取同一行冒号后的内容）用于工具名，
  保留 `_value_after`（取全部剩余内容）用于 `Action Input` / `Final Answer`。

### 问题 2：`^` 锚点不跨行导致匹配失败
- **现象**：带 `Thought:` 前缀的多行文本解析不出 `Action`。
- **原因**：正则只加了 `(?is)`，没有 MULTILINE，`^` 只匹配字符串开头。
- **解决**：改为 `(?im)`（多行模式），让 `^` 匹配每行开头。

### 问题 3：Action Input 的多行 JSON / markdown 围栏
- **现象**：LLM 常把 JSON 放在 ```json 代码块里，或折成多行，`json.loads` 直接失败。
- **解决**：解析前去掉代码块围栏；用“括号深度平衡”算法抽取第一个完整的 `{}` 对象；
  对尾随逗号、单引号做宽容修复，实在无法解析则抛 `ParseError` 并把错误反馈给 LLM 重试。

### 问题 4：工具异常如何影响循环
- **决策**：工具抛异常（除零、坏参数、工具不存在）时不中断整轮，而是把
  `错误：...` 作为 Observation 写回上下文，让 LLM 自己决定“换参数重试”还是“直接回答”。
  这更贴近真实 Agent 行为，也便于演示异常处理。

### 问题 5：观察结果在 Chat API 里用什么角色
- **决策**：文本式 ReAct 没有原生 `tool` 角色，把观察结果映射为 `role="user"` 并加
  `Observation:` 前缀（`context._to_api`）。这在 OpenAI 兼容接口下稳定可用。

### 问题 6：Session 间状态隔离
- **决策**：每个 `Session` 持有独立的 `Context`（历史）与 `TodoStore`（有状态工具数据）。
  工具通过 `ToolContext(session_id, stores)` 取到“本会话”的存储，天然隔离。

### 问题 7：Windows 控制台中文乱码
- **现象**：CLI 输出中文在 GBK 终端下乱码。
- **解决**：`cli.py` 启动时 `sys.stdout.reconfigure(encoding="utf-8")`；
  README 中建议用 `python -X utf8` 运行测试。

### 问题 8：测试里 `in` 列表误用
- **现象**：`"Final Answer: xxx" in contents`（contents 是列表）总为 False。
- **原因**：列表的 `in` 是“整元素相等”，不是子串包含。
- **解决**：改成 `any("..." in m for m in contents)`。
