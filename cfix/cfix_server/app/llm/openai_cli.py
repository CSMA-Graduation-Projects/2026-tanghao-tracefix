"""OpenAI 客户端模块，负责统一接入和适配外部大模型能力。"""

from app.llm.config import LLMRuntimeConfig
from app.llm.qwen_cli import QwenClient


class OpenAIClient(QwenClient):
    """通过 OpenAI Chat Completions 兼容接口调用模型。

    当前项目的代理层只依赖一个统一的 `chat(prompt)` 接口，
    所以这里直接复用 OpenAI 兼容协议骨架，并显式声明 provider 元信息：
    1. 保留与 Qwen / DeepSeek 一致的请求结构；
    2. 让日志与报错准确体现为 OpenAI；
    3. 为后续扩展 OpenAI 特有参数预留子类覆盖点。
    """

    provider_name = "openai"
    provider_label = "OpenAI"

    def __init__(self, config: LLMRuntimeConfig | None = None):
        super().__init__(config=config)
