"""内置工具：真实天气查询。

核心实现通过 wttr.in API（JSON 格式 j1）返回真实天气，见 get_weather()。
backend 说明：
  - "auto"（默认）：调用 wttr.in 真实查询
  - "mock"：返回内置模拟数据（用于测试 / 离线演示）
"""

from agent.core.tool import Tool


class WeatherTool(Tool):
    name = "weather"
    description = "查询指定城市的实时天气（调用 wttr.in 真实数据）。例如：北京"
    parameters = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称，例如 北京"}
        },
        "required": ["city"],
    }

    _DATA = {
        "北京": (25, "晴"),
        "上海": (28, "多云"),
        "广州": (31, "晴"),
        "深圳": (32, "阵雨"),
        "杭州": (27, "小雨"),
        "成都": (24, "阴"),
    }

    def __init__(self, backend: str = "auto") -> None:
        self.backend = backend

    def run(self, args: dict, ctx) -> str:
        city = str(args.get("city", "")).strip()
        if not city:
            return "错误：缺少 city 参数"
        if self.backend == "mock":
            temp, cond = self._DATA.get(city, (26, "晴"))
            return f"{city} 今日天气：{cond}，气温 {temp}℃，宜出行。"
        return get_weather(city)


def get_weather(city: str) -> str:
    """通过调用 wttr.in API 查询真实的天气信息（核心实现）。"""
    url = f"https://wttr.in/{city}?format=j1"

    try:
        import requests
    except ImportError:
        return "错误：未安装 requests 库，无法查询真实天气。请先 pip install requests"

    try:
        # 发起网络请求
        response = requests.get(url, timeout=10)
        # 检查响应状态码是否为 200 (成功)
        response.raise_for_status()
        # 解析返回的 JSON 数据
        data = response.json()

        # 提取当前天气状况
        current_condition = data["current_condition"][0]
        weather_desc = current_condition["weatherDesc"][0]["value"]
        temp_c = current_condition["temp_C"]

        # 格式化成自然语言返回
        return f"{city}当前天气:{weather_desc}，气温{temp_c}摄氏度"

    except requests.exceptions.RequestException as e:
        # 处理网络错误
        return f"错误:查询天气时遇到网络问题 - {e}"
    except (KeyError, IndexError) as e:
        # 处理数据解析错误
        return f"错误:解析天气数据失败，可能是城市名称无效 - {e}"
