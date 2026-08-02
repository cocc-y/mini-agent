"""LLM 客户端（OpenAI 兼容）。

使用标准库 urllib 直接调用 /chat/completions 接口，不依赖任何 SDK，
做到「核心 Agent Runtime 自行实现」。

可通过环境变量切换任意 OpenAI 兼容服务：
  LLM_BASE_URL=https://api.deepseek.com/v1
  LLM_API_KEY=sk-xxx
  LLM_MODEL=deepseek-chat
"""

import json
import urllib.error
import urllib.request

from agent.core.errors import LLMError


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        temperature: float = 0.5,
        timeout: int = 60,
    ) -> None:
        if not api_key:
            raise ValueError("api_key 不能为空，请在 .env 中配置 LLM_API_KEY")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def chat(self, messages, temperature: float = None, max_tokens: int = None) -> str:
        """发送一轮 Chat Completion 请求，返回回复文本。"""
        url = self.base_url + "/chat/completions"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise LLMError(f"HTTP {e.code}: {detail[:500]}")
        except urllib.error.URLError as e:
            raise LLMError(f"网络错误: {e.reason}")
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"请求失败: {e}")

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"响应格式异常: {payload}")
        return content or ""
