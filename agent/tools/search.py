"""内置工具：网络搜索。

优先使用真实搜索引擎 API：
  - Tavily（POST https://api.tavily.com/search）
  - SerpAPI（GET https://serpapi.com/search.json）

自动选择策略（backend="auto"）：
  1. 配置了 TAVILY_API_KEY → 用 Tavily
  2. 配置了 SERPAPI_API_KEY → 用 SerpAPI
  3. 都没有 → 降级为本地 mock 知识库（离线可用）
"""

import os

from agent.core.tool import Tool


class SearchTool(Tool):
    name = "search"
    description = (
        "搜索实时网络信息。优先使用 Tavily/SerpAPI 真实搜索"
        "（需配置 TAVILY_API_KEY 或 SERPAPI_API_KEY），未配置时使用本地知识库。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"],
    }

    _KB = {
        "python": "Python 是一种高级编程语言，于 1991 年发布，广泛用于 AI、Web 开发与自动化。",
        "agent": "AI Agent（智能体）是能够感知环境、调用工具并采取行动以实现目标的自主系统。",
        "deepseek": "DeepSeek 是深度求索公司推出的大语言模型系列，提供 OpenAI 兼容 API。",
        "北京天气": "北京今日晴，气温 25℃，空气质量优。",
        "上海天气": "上海今日多云，气温 28℃，风力 3 级。",
        "mini agent": "Mini Agent 是一个从零实现的最小可用 Agent Runtime。",
    }

    def __init__(self, backend: str = "auto") -> None:
        # "auto" | "tavily" | "serpapi" | "mock"
        self.backend = backend

    def run(self, args: dict, ctx) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "错误：缺少 query 参数"
        return self._search(query)

    # ---- 后端选择 ----

    def _resolve_backend(self) -> str:
        if self.backend != "auto":
            return self.backend
        if os.environ.get("TAVILY_API_KEY"):
            return "tavily"
        if os.environ.get("SERPAPI_API_KEY"):
            return "serpapi"
        return "mock"

    def _search(self, query: str) -> str:
        backend = self._resolve_backend()
        if backend == "tavily":
            return search_tavily(query, os.environ.get("TAVILY_API_KEY", ""))
        if backend == "serpapi":
            return search_serpapi(query, os.environ.get("SERPAPI_API_KEY", ""))
        return self._mock(query)

    # ---- mock 降级 ----

    def _mock(self, query: str) -> str:
        q = query.lower()
        hits = {k: v for k, v in self._KB.items() if q in k.lower() or q in v.lower()}
        if not hits:
            return f"未找到与“{query}”相关的搜索结果。"
        return "\n".join(f"- {k}: {v}" for k, v in hits.items())


def search_tavily(query: str, api_key: str) -> str:
    """通过 Tavily Search API 搜索。"""
    if not api_key:
        return "错误：未配置 TAVILY_API_KEY，无法使用 Tavily 搜索。"
    try:
        import requests
    except ImportError:
        return "错误：未安装 requests 库，无法进行网络搜索。请先 pip install requests"

    url = "https://api.tavily.com/search"
    payload = {"api_key": api_key, "query": query, "max_results": 5}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return f"错误:搜索请求失败 - {e}"

    results = data.get("results", [])
    if not results:
        return f"未找到与“{query}”相关的搜索结果。"
    lines = [
        f"- {r.get('title', '')}: {r.get('content', '')[:300]}" for r in results[:5]
    ]
    return "\n".join(lines)


def search_serpapi(query: str, api_key: str) -> str:
    """通过 SerpAPI（Google 搜索）查询。"""
    if not api_key:
        return "错误：未配置 SERPAPI_API_KEY，无法使用 SerpAPI 搜索。"
    try:
        import requests
    except ImportError:
        return "错误：未安装 requests 库，无法进行网络搜索。请先 pip install requests"

    url = "https://serpapi.com/search.json"
    params = {"engine": "google", "q": query, "api_key": api_key}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return f"错误:搜索请求失败 - {e}"

    results = data.get("organic_results", [])
    if not results:
        return f"未找到与“{query}”相关的搜索结果。"
    lines = [
        f"- {r.get('title', '')}: {r.get('snippet', r.get('content', ''))[:300]}"
        for r in results[:5]
    ]
    return "\n".join(lines)
