"""模型配置领域的请求与响应模型定义，约束前后端交互数据结构。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelCfgSaveIn(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str
    name: str | None = None
    model_key: str
    base_url: str
    api_key: str | None = None
    max_tok: int = Field(default=4096, ge=1, le=32768)
    temp: float | None = Field(default=None, ge=0.0, le=2.0)
    enabled: bool = True
    is_active: bool = True

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return str(value or "").strip().lower()

    @field_validator("model_key", "base_url")
    @classmethod
    def require_text(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("字段不能为空")
        return text


class ModelCfgProviderOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str
    label: str
    default_model_key: str
    default_base_url: str
    default_max_tok: int
    default_temp: float


class ModelCfgMaskedOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: int | None = None
    provider: str
    name: str
    model_key: str
    base_url: str
    max_tok: int
    temp: float
    enabled: bool
    is_active: bool
    has_api_key: bool
    api_key_masked: str