"""工具单元测试：calculator / search / todo / weather。

search 与 weather 的「真实后端」测试通过 mock requests 完成，
不发起真实网络请求。
"""

from unittest.mock import patch

from agent.core.tool import ToolContext
from agent.tools.calculator import CalculatorTool
from agent.tools.search import SearchTool, search_serpapi, search_tavily
from agent.tools.todo import TodoStore, TodoTool
from agent.tools.weather import WeatherTool, get_weather


# ---- calculator ----

def test_calculator_basic():
    tool = CalculatorTool()
    assert tool.run({"expression": "3*7"}, None) == "21"
    assert tool.run({"expression": "3.5 * (2 + 4) / 7"}, None) == "3"
    assert tool.run({"expression": "2 ** 10"}, None) == "1024"
    assert tool.run({"expression": "sqrt(9) + pi"}, None) is not None


def test_calculator_missing_param():
    tool = CalculatorTool()
    assert "错误" in tool.run({}, None)


def test_calculator_rejects_code_injection():
    tool = CalculatorTool()
    assert "错误" in tool.run({"expression": "__import__('os').system('dir')"}, None)
    assert "错误" in tool.run({"expression": "1; import os"}, None)
    assert "错误" in tool.run({"expression": "open('x')"}, None)


def test_calculator_division_by_zero():
    tool = CalculatorTool()
    assert "错误" in tool.run({"expression": "1/0"}, None)


# ---- search ----

def test_search_mock_found():
    tool = SearchTool(backend="mock")
    out = tool.run({"query": "python"}, None)
    assert "Python" in out


def test_search_mock_not_found():
    tool = SearchTool(backend="mock")
    out = tool.run({"query": "不存在的关键词xyz"}, None)
    assert "未找到" in out


def test_search_backend_resolution(monkeypatch):
    tool = SearchTool()  # auto
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    assert tool._resolve_backend() == "mock"

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    assert tool._resolve_backend() == "tavily"

    monkeypatch.delenv("TAVILY_API_KEY")
    monkeypatch.setenv("SERPAPI_API_KEY", "serp-test")
    assert tool._resolve_backend() == "serpapi"


def test_search_tavily_missing_key():
    assert "TAVILY_API_KEY" in search_tavily("python", "")


def test_search_tavily_success():
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [
                {"title": "标题1", "content": "内容1"},
                {"title": "标题2", "content": "内容2"},
            ]}

    with patch("requests.post", return_value=FakeResp()):
        out = search_tavily("python", "fake-key")
    assert "标题1" in out and "内容1" in out
    assert "标题2" in out


def test_search_serpapi_missing_key():
    assert "SERPAPI_API_KEY" in search_serpapi("python", "")


def test_search_serpapi_success():
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"organic_results": [
                {"title": "结果A", "snippet": "片段A"},
            ]}

    with patch("requests.get", return_value=FakeResp()):
        out = search_serpapi("agent", "fake-key")
    assert "结果A" in out and "片段A" in out


# ---- todo ----

def test_todo_flow():
    store = TodoStore()
    ctx = ToolContext(session_id="s1", stores={"todo": store})
    tool = TodoTool()

    assert "已添加" in tool.run({"action": "add", "item": "买牛奶"}, ctx)
    tool.run({"action": "add", "item": "写周报"}, ctx)

    out = tool.run({"action": "list"}, ctx)
    assert "买牛奶" in out and "写周报" in out

    assert "完成" in tool.run({"action": "done", "index": 1}, ctx)
    out = tool.run({"action": "list"}, ctx)
    assert "[x]" in out

    tool.run({"action": "remove", "index": 1}, ctx)
    assert len(store.items) == 1


def test_todo_bad_index():
    store = TodoStore()
    ctx = ToolContext(session_id="s1", stores={"todo": store})
    tool = TodoTool()
    assert "错误" in tool.run({"action": "done", "index": 5}, ctx)


# ---- weather ----

def test_weather_mock():
    tool = WeatherTool(backend="mock")
    out = tool.run({"city": "北京"}, None)
    assert "北京" in out and "℃" in out
    # 未收录城市也有默认返回
    assert "℃" in tool.run({"city": "火星"}, None)


def test_weather_missing_city():
    tool = WeatherTool(backend="mock")
    assert "错误" in tool.run({}, None)


def test_weather_real_success():
    """wttr.in 核心实现：mock requests 返回数据。"""
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"current_condition": [
                {"weatherDesc": [{"value": "晴"}], "temp_C": "25"}
            ]}

    with patch("requests.get", return_value=FakeResp()):
        out = get_weather("北京")
    assert "北京当前天气" in out and "晴" in out and "25" in out


def test_weather_real_network_error():
    class BoomResp:
        def raise_for_status(self):
            import requests

            raise requests.exceptions.RequestException("boom")

    with patch("requests.get", return_value=BoomResp()):
        out = get_weather("北京")
    assert "错误" in out


def test_weather_real_parse_error():
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {}  # 缺少 current_condition

    with patch("requests.get", return_value=FakeResp()):
        out = get_weather("北京")
    assert "错误" in out
