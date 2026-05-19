"""Qwen 客户端模块，负责统一接入和适配外部大模型能力。"""

import json
import time
from urllib import error, request

from app.llm.config import LLMRuntimeConfig, get_env_llm_config
from app.llm.base import LLMBase


class QwenClient(LLMBase):
    """通过阿里云百炼 OpenAI 兼容接口调用 Qwen。

    这版围绕“真链路稳化”补了 4 个点：
    1. 支持简单重试；
    2. 支持 content 为字符串或分片数组；
    3. 自动清理 `<think>`；
    4. 对空返回和结构异常给出明确错误。
    """

    provider_name = "qwen"
    provider_label = "Qwen"

    def __init__(self, config: LLMRuntimeConfig | None = None):
        self.config = config or get_env_llm_config()
        self.base_url = self._normalize_base_url(self.config.base_url)
        self.api_key = self.config.api_key
        self.model = self.config.model
        self.timeout = self.config.timeout
        self.temperature = self.config.temperature
        self.max_tokens = self.config.max_tokens
        self.retry_count = max(0, int(self.config.retry_count or 0))
        self.retry_backoff_sec = float(self.config.retry_backoff_sec or 0)
        self.strip_think_enabled = bool(self.config.strip_think)

    @classmethod
    def _normalize_base_url(cls, raw_url: str) -> str:
        url = str(raw_url or "").strip().rstrip("/")
        suffix = "/chat/completions"
        if url.lower().endswith(suffix):
            url = url[: -len(suffix)]
        return url

    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _request_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, messages: list[dict]) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    @staticmethod
    def _content_to_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    # 兼容 OpenAI 风格的 text 分片。
                    if item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    elif "text" in item:
                        parts.append(str(item.get("text", "")))
                    elif "content" in item:
                        parts.append(str(item.get("content", "")))
                else:
                    parts.append(str(item))
            return "\n".join(x for x in parts if x)
        return str(content or "")

    def _post_once(self, payload: dict) -> dict:
        req = request.Request(
            url=self._chat_url(),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=self._request_headers(),
        )
        with request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self.config.is_ready:
            raise RuntimeError(f"{self.provider_label} 未配置完成，无法调用当前模型：{self.model}")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = self._build_payload(messages)

        last_err = None
        for attempt in range(self.retry_count + 1):
            try:
                body = self._post_once(payload)
                content = self._content_to_text(body["choices"][0]["message"]["content"])
                cleaned = self.strip_think(content) if self.strip_think_enabled else (content or "").strip()
                if cleaned.strip():
                    return cleaned.strip()
                raise RuntimeError(f"{self.provider_label} 返回为空：{body}")
            except error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else str(exc)
                last_err = RuntimeError(f"{self.provider_label} HTTP 调用失败：{detail}")
            except Exception as exc:  # noqa: BLE001
                last_err = RuntimeError(f"{self.provider_label} 调用失败：{exc}")

            if attempt < self.retry_count and self.retry_backoff_sec > 0:
                time.sleep(self.retry_backoff_sec * (attempt + 1))

        raise last_err or RuntimeError(f"{self.provider_label} 调用失败：未知错误")
