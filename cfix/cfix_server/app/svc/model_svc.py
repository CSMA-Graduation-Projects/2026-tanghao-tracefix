from __future__ import annotations

import base64
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.cfg import settings
from app.llm.config import LLMRuntimeConfig, get_env_llm_config
from app.llm.factory import get_llm_client
from app.models.model_cfg import ModelCfg
from app.repo.model_repo import (
    deactivate_user_model_cfgs,
    get_active_model_cfg,
    get_model_cfg_by_id,
    get_user_model_cfg_by_provider,
    list_user_model_cfgs,
    save_model_cfg,
)


PROVIDER_PRESETS = {
    "qwen": {
        "label": "Qwen",
        "default_model_key": "qwen3-coder-next",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_max_tok": 4096,
        "default_temp": 0.2,
    },
    "deepseek": {
        "label": "DeepSeek",
        "default_model_key": "deepseek-chat",
        "default_base_url": "https://api.deepseek.com/v1",
        "default_max_tok": 4096,
        "default_temp": 0.2,
    },
    "openai": {
        "label": "OpenAI",
        "default_model_key": "gpt-4.1-mini",
        "default_base_url": "https://api.openai.com/v1",
        "default_max_tok": 4096,
        "default_temp": 0.2,
    },
}


def _provider_meta(provider: str) -> dict:
    key = str(provider or "").strip().lower()
    if key not in PROVIDER_PRESETS:
        raise ValueError("暂不支持该模型提供方")
    return {"provider": key, **PROVIDER_PRESETS[key]}


def _fernet() -> Fernet:
    secret = (settings.jwt_secret or "cfix-llm-secret").encode("utf-8")
    return Fernet(base64.urlsafe_b64encode(sha256(secret).digest()))


def encrypt_api_key(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    return _fernet().encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_api_key(cipher_text: str | None) -> str:
    token = str(cipher_text or "").strip()
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def mask_api_key(raw: str | None) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if len(text) <= 6:
        if len(text) <= 2:
            return "*" * len(text)
        return text[:1] + ("*" * (len(text) - 2)) + text[-1:]
    return text[:3] + ("*" * max(4, len(text) - 6)) + text[-3:]


def pack_model_cfg(row: ModelCfg | None) -> dict:
    if not row:
        return {}
    api_key = decrypt_api_key(getattr(row, "api_key_enc", None))
    return {
        "id": row.id,
        "provider": row.provider,
        "name": row.name,
        "model_key": row.model_key,
        "base_url": row.base_url or "",
        "max_tok": int(row.max_tok or 0),
        "temp": round(float(row.temp or 0) / 100.0, 2),
        "enabled": bool(row.enabled),
        "is_active": bool(row.is_active),
        "has_api_key": bool(api_key),
        "api_key_masked": mask_api_key(api_key),
    }


def list_provider_options() -> list[dict]:
    return [
        {
            "provider": key,
            "label": value["label"],
            "default_model_key": value["default_model_key"],
            "default_base_url": value["default_base_url"],
            "default_max_tok": value["default_max_tok"],
            "default_temp": value["default_temp"],
        }
        for key, value in PROVIDER_PRESETS.items()
    ]


def _pick_runtime_model_cfg(rows: list[ModelCfg]) -> ModelCfg | None:
    active = next((row for row in rows if row.is_active and row.enabled), None)
    if active:
        return active

    enabled_rows = [row for row in rows if row.enabled]
    if not enabled_rows:
        return None
    return max(enabled_rows, key=lambda item: int(getattr(item, "id", 0) or 0))


def resolve_default_model_id(db: Session, user_id: int) -> int | None:
    row = _pick_runtime_model_cfg(list_user_model_cfgs(db, user_id))
    return row.id if row and row.enabled else None


def resolve_model_cfg_for_user(db: Session, user_id: int, *, model_id: int | None = None) -> ModelCfg | None:
    if model_id is not None:
        row = get_model_cfg_by_id(db, int(model_id))
        if row and (row.user_id is None or int(row.user_id) == int(user_id)):
            return row
    return _pick_runtime_model_cfg(list_user_model_cfgs(db, user_id))


def resolve_llm_runtime_config(db: Session | None = None, *, user_id: int | None = None, model_id: int | None = None) -> LLMRuntimeConfig:
    if db is not None and user_id is not None:
        row = resolve_model_cfg_for_user(db, user_id, model_id=model_id)
        if row:
            return LLMRuntimeConfig(
                provider=row.provider,
                model=row.model_key,
                base_url=row.base_url or "",
                api_key=decrypt_api_key(row.api_key_enc),
                timeout=settings.llm_timeout,
                temperature=round(float(row.temp or 0) / 100.0, 2),
                max_tokens=int(row.max_tok or 4096),
                retry_count=max(0, int(settings.llm_retry_count or 0)),
                retry_backoff_sec=float(settings.llm_retry_backoff_sec or 0),
                strip_think=bool(settings.llm_strip_think),
                enabled=bool(row.enabled),
                strict=bool(settings.llm_strict),
            )
    return get_env_llm_config()


def resolve_llm_client(db: Session | None = None, *, user_id: int | None = None, model_id: int | None = None):
    config = resolve_llm_runtime_config(db, user_id=user_id, model_id=model_id)
    return get_llm_client(config) if config.is_ready else None


class ModelService:
    def get_user_settings(self, db: Session, user_id: int) -> dict:
        rows = list_user_model_cfgs(db, user_id)
        configs = {row.provider: pack_model_cfg(row) for row in rows}
        active = _pick_runtime_model_cfg(rows)
        return {
            "active_provider": active.provider if active else "",
            "active_model_id": active.id if active else None,
            "providers": list_provider_options(),
            "configs": configs,
        }

    def save_user_config(self, db: Session, user_id: int, payload) -> dict:
        meta = _provider_meta(payload.provider)
        row = get_user_model_cfg_by_provider(db, user_id, meta["provider"])
        is_new = row is None
        current_active = get_active_model_cfg(db, user_id)
        if row is None:
            row = ModelCfg(
                user_id=user_id,
                provider=meta["provider"],
                name=meta["label"],
                model_key=meta["default_model_key"],
                base_url=meta["default_base_url"],
                temp=int(round(float(meta["default_temp"]) * 100)),
                max_tok=int(meta["default_max_tok"]),
                enabled=True,
                is_active=False,
            )

        api_key = str(getattr(payload, "api_key", "") or "").strip()
        if api_key:
            row.api_key_enc = encrypt_api_key(api_key)
        elif is_new or not row.api_key_enc:
            raise ValueError("API Key 不能为空")

        row.name = str(getattr(payload, "name", "") or meta["label"]).strip() or meta["label"]
        row.model_key = str(getattr(payload, "model_key", "") or meta["default_model_key"]).strip() or meta["default_model_key"]
        row.base_url = str(getattr(payload, "base_url", "") or meta["default_base_url"]).strip() or meta["default_base_url"]
        row.max_tok = max(1, min(int(getattr(payload, "max_tok", meta["default_max_tok"]) or meta["default_max_tok"]), 32768))
        temp = getattr(payload, "temp", None)
        row.temp = int(round(float(meta["default_temp"] if temp is None else temp) * 100))
        row.enabled = bool(getattr(payload, "enabled", True))

        wants_active = bool(getattr(payload, "is_active", True))
        has_no_active = current_active is None
        keeps_current_active = bool(current_active and current_active.id == getattr(row, "id", None) and row.enabled)
        row.is_active = bool(row.enabled and (wants_active or has_no_active or keeps_current_active))

        saved = save_model_cfg(db, row)
        if saved.is_active:
            deactivate_user_model_cfgs(db, user_id, exclude_id=saved.id)
            saved = get_model_cfg_by_id(db, saved.id) or saved

        return {
            "saved": pack_model_cfg(saved),
            **self.get_user_settings(db, user_id),
        }