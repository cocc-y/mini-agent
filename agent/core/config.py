"""运行时配置。

通过环境变量或 .env 文件加载，核心只依赖标准库（不依赖 python-dotenv）。
"""

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"  # OpenAI 兼容接口，可替换
    model: str = "deepseek-chat"
    temperature: float = 0.5
    timeout: int = 60
    max_rounds: int = 6          # 单个用户请求允许的最大工具迭代轮数
    max_history_messages: int = 16  # 完整保留的历史消息条数，超出部分触发压缩
    verbose: bool = True


def load_env(path: str = ".env") -> None:
    """读取 .env（若存在），已存在的环境变量不覆盖。"""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, "") or default


def config_from_env() -> AgentConfig:
    return AgentConfig(
        api_key=_get("LLM_API_KEY", _get("OPENAI_API_KEY", "")),
        base_url=_get("LLM_BASE_URL", "https://api.deepseek.com/v1"),
        model=_get("LLM_MODEL", "deepseek-chat"),
        temperature=float(_get("LLM_TEMPERATURE", "0.5")),
        timeout=int(_get("LLM_TIMEOUT", "60")),
        max_rounds=int(_get("MAX_ROUNDS", "6")),
        max_history_messages=int(_get("MAX_HISTORY_MESSAGES", "16")),
    )
