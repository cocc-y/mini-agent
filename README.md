# Mini Agent — 从零实现的最小可用 Agent Runtime

一个不依赖任何现有 Agent 框架（langgraph / openhands / openclaw）的极简 Agent。
核心 Agent Runtime（LLM 输出解析、工具注册与调用、Agent 循环、上下文管理、
Session 管理），仅调用真实 LLM 的 Chat Completions 接口。

```
用户输入 ──► LLM 决策 ──► 调用工具 ──► 观察结果 ──► 继续循环 / 返回答案
```

## 功能一览

| 需求 | 实现位置 |
|---|---|
| 基本循环（收输入 → 判断直接回复/调工具 → 调工具 → 继续/返回） | `agent/core/loop.py` |
| 4 个工具：calculator / search / todo / weather | `agent/tools/` |
| 工具注册机制（名称 + 描述 + 参数 Schema） | `agent/core/tool.py` |
| LLM 输出解析（提取思考 / 工具调用 / 最终答案） | `agent/core/parser.py` |
| 多 Session 独立（窗口 1/2 互不影响） | `agent/core/session.py` |
| 上下文管理（历史记忆、追问、最大轮数、基础压缩） | `agent/core/context.py` |
| 基本异常处理 | `agent/core/loop.py` + 各工具 |
| 工具调用 Trace / 执行日志 | `agent/core/trace.py` + CLI `/trace` |
| 测试用例（53 个） | `tests/` |

## 运行方式

### 1. 安装

仅需 Python 3.10+（核心运行时不依赖第三方库）。测试需要 pytest：

```bash
python -m pip install -r requirements.txt     
```

### 2. 配置真实 LLM API

复制 `.env.example` 为 `.env`，填入你的 Key 与模型：

```bash
cp .env.example .env
```

```ini
LLM_API_KEY=REPLACE_WITH_YOUR_API_KEY
LLM_BASE_URL=https://api.deepseek.com/v1   # OpenAI 兼容接口均可
LLM_MODEL=deepseek-chat
```

> 兼容任意 OpenAI 格式服务：OpenAI、DeepSeek、通义千问、Moonshot、国产中转/自建
> （vLLM / Ollama）等，只要接口是 `POST {base_url}/chat/completions`。

也可以直接使用环境变量，不写 `.env`。

### 3. 工具的真实 API（可选）

```ini
# 真实网络搜索：Tavily / SerpAPI 配置其一即可
TAVILY_API_KEY=tvly-xxxx
#SERPAPI_API_KEY=xxxx
```

- **search**：配置了 `TAVILY_API_KEY` 用 Tavily，否则配置了 `SERPAPI_API_KEY` 用 SerpAPI；
  两者都没有时自动降级为本地 mock 知识库。
- **weather**：直接调用 [wttr.in](https://wttr.in) 实时天气 API（无需 Key）。
- 需要安装 `requests`（已写入 `requirements.txt`）。

### 3. 启动 CLI

```bash
python -m agent.cli
```

```
__  __ _       _        ___   _   _
...
你> 3.5*(2+4)/7 等于多少？
Agent > 3.5*(2+4)/7 等于 3.0
```

### 4. 运行测试

```bash
python -X utf8 -m pytest -q
```

## 多 Session 使用（CLI 演示）

```
你> /new              # 创建并切换到新会话（相当于开新窗口）
你> 帮我记待办：写周报
你> /switch s-xxxxxxxx  # 切回旧会话，历史与待办都还在
你> /list              # 列出所有会话
你> /trace             # 打印当前会话完整执行 Trace
```

- 不同 Session 拥有**独立**的 `Context`（对话历史）与 `TodoStore`（待办数据），互不影响。
- 同一个 Session 内随时继续聊，历史上下文自动带上下一轮的思考、工具结果与结论，
  因此既支持**纯对话追问**，也支持**带着工具的追问**（如“刚才那个数再乘 2”）。
- 命令：`/help /new /list /switch <id> /delete <id> /trace /stats /quit`

## 系统设计

```
agent/
├── core/                    # 核心 Agent Runtime
│   ├── llm.py               # LLM 客户端：标准库 urllib 直连 /chat/completions
│   ├── parser.py            # LLM 输出解析：提取 思考 / 工具调用 / 最终答案
│   ├── tool.py              # 工具框架：Tool 基类 + ToolRegistry（注册/校验/执行）
│   ├── context.py           # 上下文：历史、摘要、压缩、组装发给 LLM 的消息
│   ├── session.py           # Session 管理：多会话隔离
│   ├── loop.py              # Agent 主循环 + System Prompt 生成
│   ├── trace.py             # Trace 日志
│   ├── message.py           # 内部消息结构
│   ├── config.py            # 配置加载（.env / 环境变量）
│   └── errors.py            # 统一异常类型
├── tools/                   # 内置工具（均为 Tool 子类）
│   ├── calculator.py        # 安全计算器（AST 白名单，防注入）
│   ├── search.py            # 真实网络搜索：Tavily / SerpAPI，未配置时降级 mock
│   ├── todo.py              # 待办（按 Session 隔离的有状态存储）
│   └── weather.py           # 真实天气：wttr.in API（含 mock 测试后端）
└── cli.py                   # 命令行交互入口
```

### Agent 循环（`loop.py`）

1. 接收用户输入，写入当前轮上下文；
2. 组装 `[system(工具 Schema + 格式说明)] + [摘要] + [历史轮次] + [当前轮]` 发给 LLM；
3. 解析 LLM 输出：
   - 有 `Action + Action Input` → 校验并执行工具，把**观察结果**追加进上下文，**继续循环**；
   - 有 `Final Answer` → 记录最终答案，本轮结束，**返回给用户**；
   - 解析失败 / 工具异常 → 把错误作为观察喂回 LLM，让它自行修正；
4. 循环受 `max_rounds`（默认 6）限制，防止无限迭代。

### 工具注册机制（`tool.py`）

每个工具是一个 `Tool` 子类，声明 `name`、`description`、`parameters`（JSON Schema）：

```python
class CalculatorTool(Tool):
    name = "calculator"
    description = "计算数学表达式，例如 3.5 * (2 + 4) / 7"
    parameters = {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    }
    def run(self, args, ctx) -> str: ...
```

`ToolRegistry` 负责注册、去重、按 Schema 校验必填参数，并把全部工具的
**描述 + 参数 Schema** 渲染进 System Prompt，LLM 据此自主决策调用哪个工具、传什么参数。

### LLM 输出解析（`parser.py`）

LLM 被要求输出结构化文本（ReAct 风格，兼容中英文标记）：

```
Thought: 我需要计算一下
Action: calculator
Action Input: {"expression": "3.5 * (2 + 4) / 7"}
```

```
Thought: 结果算出来了
Final Answer: 3.5*(2+4)/7 = 3.0
```

解析器提取三类结果：
- `tool_call`：思考 + 工具名 + 参数（JSON 用平衡括号算法提取，兼容多行与 markdown 围栏）；
- `final_answer`：思考 + 最终答案（支持多行）；
- `raw`：两者都没有时，直接把原文当答案。

### 上下文与 Memory（`context.py`）

放进上下文的信息（按顺序）：
1. **System Prompt**：工具描述 + 参数 Schema + 输出格式约束；
2. **摘要**：更早对话被压缩后的“背景记忆”；
3. **历史轮次**：之前每轮完整保留的 用户输入 / 思考+工具调用 / 工具观察 / 最终答案；
4. **当前轮**：正在处理的这一轮的各类消息。

**支持追问的原因**：完整轮次被保留在历史里，下一轮发起请求时全部带回去，
所以“纯对话追问”和“带工具的追问”都能理解上下文。

**基础压缩**：当历史消息总数超过 `MAX_HISTORY_MESSAGES`（默认 16）时，最早的一整轮
被抽出来压缩成一段摘要（优先用 LLM 生成，失败时退化为“抽取式压缩”：只保留
用户输入、工具结果、最终答案并截断长度），放在第 2 步的位置，相当于“长期记忆”。

**最大轮次限制**：`MAX_ROUNDS`（默认 6）限制单个用户请求内的工具迭代次数。

> 说明：以上是 Agent 内部的“对话记忆”。本题目不涉及跨会话的持久化用户画像
> （本项目的 Memory 机制等价于“同一会话的历史 + 压缩摘要”）。

## 测试用例（`tests/`）

| 文件 | 覆盖内容 |
|---|---|
| `test_tools.py` | 4 个工具的正确性、参数缺失、注入防护、除零；search 后端选择/降级；Tavily/SerpAPI/wttr.in 真实后端（mock requests） |
| `test_registry.py` | 注册/去重/未知工具/必填校验/Schema 渲染 |
| `test_parser.py` | 思考/工具调用/最终答案提取、多行、markdown 围栏、中文标记、坏 JSON |
| `test_context.py` | 历史保留、Observation 角色映射、压缩触发、摘要生成 |
| `test_session.py` | 创建/查询/删除/隔离/切回继续聊 |
| `test_loop.py` | 完整循环：工具→观察→答案、直接回复、裸文本、纯对话追问、带工具追问、多工具串联、最大轮数、工具异常、解析失败恢复、未知工具、LLM 故障、Session 隔离 |

测试通过 `MockLLM`（脚本化返回预设回复并记录请求）驱动，不依赖真实网络。

## 提交内容对照

- **真实 LLM API**：`agent/core/llm.py` 直连 Chat Completions；填入 `.env` 即可运行。
- **代码链接**：本目录即为完整代码（可用 Git 初始化并推到远端仓库）。
- **操作录屏**：运行 `python -m agent.cli`，依次演示：
  1. 会话 1：查天气 → 记待办 → 追问；
  2. `/new` 开启会话 2：写周报待办；
  3. `/switch` 切回会话 1 继续追问（验证 Session 独立与上下文保留）；
  4. `/trace` 查看工具调用 Trace。
- **README**：本文档。
- **AI Prompt 与问题解决记录**：见 [`PROMPTS.md`](PROMPTS.md)。
