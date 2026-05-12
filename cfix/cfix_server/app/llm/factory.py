from app.llm.config import LLMRuntimeConfig, get_env_llm_config
from app.llm.deepseek_cli import DeepSeekClient
from app.llm.openai_cli import OpenAIClient
from app.llm.qwen_cli import QwenClient


def get_llm_client(config: LLMRuntimeConfig | None = None):
    runtime = config or get_env_llm_config()
    provider = runtime.normalized_provider
    if provider == "qwen":
        return QwenClient(runtime)
    if provider == "openai":
        return OpenAIClient(runtime)
    if provider == "deepseek":
        return DeepSeekClient(runtime)
    raise ValueError(f"不支持的 LLM_PROVIDER: {runtime.provider}")
