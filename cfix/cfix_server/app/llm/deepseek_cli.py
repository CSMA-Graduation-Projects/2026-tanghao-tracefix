from app.llm.config import LLMRuntimeConfig
from app.llm.qwen_cli import QwenClient


class DeepSeekClient(QwenClient):
    """通过 DeepSeek OpenAI 兼容接口调用模型。

    DeepSeek 当前同样走 `/chat/completions` 协议，
    所以这里复用统一的 HTTP 骨架，但补齐独立的 provider 元信息：
    1. 让运行时错误与调试信息准确体现为 DeepSeek；
    2. 保持和其他 provider 完全一致的调用入口；
    3. 后续若要增加 DeepSeek 专属参数，可直接在该类覆盖请求构造。
    """

    provider_name = "deepseek"
    provider_label = "DeepSeek"

    def __init__(self, config: LLMRuntimeConfig | None = None):
        super().__init__(config=config)
