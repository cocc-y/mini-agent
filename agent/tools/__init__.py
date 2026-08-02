"""内置工具包。"""

from agent.tools.calculator import CalculatorTool
from agent.tools.search import SearchTool, search_serpapi, search_tavily
from agent.tools.todo import TodoStore, TodoTool
from agent.tools.weather import WeatherTool, get_weather

DEFAULT_TOOLS = [CalculatorTool(), SearchTool(), TodoTool(), WeatherTool()]

__all__ = [
    "CalculatorTool",
    "SearchTool",
    "search_serpapi",
    "search_tavily",
    "TodoTool",
    "TodoStore",
    "WeatherTool",
    "get_weather",
    "DEFAULT_TOOLS",
]
