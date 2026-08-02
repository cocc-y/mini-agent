"""内置工具：待办事项（有状态，按 session 隔离）。"""

from agent.core.tool import Tool


class TodoStore:
    """每个 Session 一份，实现会话之间的状态隔离。"""

    def __init__(self) -> None:
        self.items = []  # list[{"text": str, "done": bool}]

    def add(self, text: str) -> str:
        self.items.append({"text": text, "done": False})
        return f"已添加待办：{text}（当前共 {len(self.items)} 条）"

    def list(self) -> str:
        if not self.items:
            return "待办列表为空。"
        lines = [
            f"{i + 1}. [{'x' if it['done'] else ' '}] {it['text']}"
            for i, it in enumerate(self.items)
        ]
        return "待办列表：\n" + "\n".join(lines)

    def done(self, index: int) -> str:
        it = self._get(index)
        it["done"] = True
        return f"已将待办标记为完成：{it['text']}"

    def remove(self, index: int) -> str:
        it = self._get(index)
        self.items.pop(index - 1)
        return f"已删除待办：{it['text']}"

    def _get(self, index: int) -> dict:
        if not isinstance(index, int) or not (1 <= index <= len(self.items)):
            raise ValueError(f"序号不合法，应在 1..{len(self.items)} 之间")
        return self.items[index - 1]


class TodoTool(Tool):
    name = "todo"
    description = "管理待办事项。action 支持 add(添加)、list(列出)、done(标记完成)、remove(删除)。"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "done", "remove"],
                "description": "要执行的动作",
            },
            "item": {
                "type": "string",
                "description": "待办内容（action 为 add 时必填）",
            },
            "index": {
                "type": "integer",
                "description": "序号（action 为 done/remove 时必填，从 1 开始）",
            },
        },
        "required": ["action"],
    }

    def run(self, args: dict, ctx) -> str:
        store = ctx.stores.get("todo") if ctx else None
        if store is None:
            return "错误：当前会话没有可用的 todo 存储。"
        action = args.get("action")
        try:
            if action == "add":
                return store.add(str(args.get("item", "")).strip())
            if action == "list":
                return store.list()
            if action == "done":
                return store.done(args.get("index"))
            if action == "remove":
                return store.remove(args.get("index"))
        except Exception as e:  # noqa: BLE001
            return f"错误：{e}"
        return f"错误：未知动作 {action!r}（可选：add / list / done / remove）"
