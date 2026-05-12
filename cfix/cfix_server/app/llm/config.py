from dataclasses import dataclass

from app.core.cfg import settings


@dataclass
class LLMRuntimeConfig:
    provider: str = "qwen"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    timeout: int = 120
    temperature: float = 0.2
    max_tokens: int = 4096
    retry_count: int = 2
    retry_backoff_sec: float = 1.0
    strip_think: bool = True
    enabled: bool = True
    strict: bool = False

    @property
    def normalized_provider(self) -> str:
        return (self.provider or "qwen").strip().lower()

    @property
    def is_ready(self) -> bool:
        return bool(self.enabled and self.api_key and self.base_url and self.model)


def get_env_llm_config() -> LLMRuntimeConfig:
    return LLMRuntimeConfig(
        provider=settings.llm_provider,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        retry_count=max(0, int(settings.llm_retry_count or 0)),
        retry_backoff_sec=float(settings.llm_retry_backoff_sec or 0),
        strip_think=bool(settings.llm_strip_think),
        enabled=bool(settings.llm_enable),
        strict=bool(settings.llm_strict),
    )