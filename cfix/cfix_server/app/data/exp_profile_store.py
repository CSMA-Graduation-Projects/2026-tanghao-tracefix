from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

_STORE_PATH = Path(__file__).resolve().parent / 'exp_profiles.json'
_DEFAULT_KEY = 'full_chain'

_PROFILE_MAP: dict[str, dict] = {
    'no_feedback_single': {
        'key': 'no_feedback_single',
        'label': '无反馈单轮生成',
        'short_label': '单轮基线',
        'desc': '只生成一次代码并直接测试，用来观察初始通过情况。',
        'iterative': False,
        'trace_on': False,
        'lesson_on': False,
        'rollback_on': False,
        'features': [
            {'key': 'gen_once', 'label': '单轮生成', 'enabled': True},
            {'key': 'error_feedback', 'label': '错误反馈修复', 'enabled': False},
            {'key': 'trace', 'label': 'Trace', 'enabled': False},
            {'key': 'lesson', 'label': 'Lesson', 'enabled': False},
            {'key': 'rollback', 'label': 'Rollback', 'enabled': False},
        ],
    },
    'error_feedback_iter': {
        'key': 'error_feedback_iter',
        'label': '只有错误反馈的多轮修复',
        'short_label': '错误反馈多轮',
        'desc': '失败后仅使用结构化错误反馈做多轮修复，不启用 Trace、Lesson 和 Rollback。',
        'iterative': True,
        'trace_on': False,
        'lesson_on': False,
        'rollback_on': False,
        'features': [
            {'key': 'gen_once', 'label': '单轮生成', 'enabled': True},
            {'key': 'error_feedback', 'label': '错误反馈修复', 'enabled': True},
            {'key': 'trace', 'label': 'Trace', 'enabled': False},
            {'key': 'lesson', 'label': 'Lesson', 'enabled': False},
            {'key': 'rollback', 'label': 'Rollback', 'enabled': False},
        ],
    },
    'full_chain': {
        'key': 'full_chain',
        'label': 'trace + lesson + rollback 完整链路',
        'short_label': '完整链路',
        'desc': '启用 Trace、Lesson 和 Rollback，观察完整机制是否比前两组更稳定。',
        'iterative': True,
        'trace_on': True,
        'lesson_on': True,
        'rollback_on': True,
        'features': [
            {'key': 'gen_once', 'label': '单轮生成', 'enabled': True},
            {'key': 'error_feedback', 'label': '错误反馈修复', 'enabled': True},
            {'key': 'trace', 'label': 'Trace', 'enabled': True},
            {'key': 'lesson', 'label': 'Lesson', 'enabled': True},
            {'key': 'rollback', 'label': 'Rollback', 'enabled': True},
        ],
    },
}


def _default_store() -> dict:
    return {
        'profiles': {},
    }


def _ensure_store_file() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _STORE_PATH.exists():
        _STORE_PATH.write_text(json.dumps(_default_store(), ensure_ascii=False, indent=2), encoding='utf-8')


def _load_store() -> dict:
    _ensure_store_file()
    try:
        raw = json.loads(_STORE_PATH.read_text(encoding='utf-8') or '{}')
    except Exception:
        raw = {}
    store = _default_store()
    if isinstance(raw, dict) and isinstance(raw.get('profiles'), dict):
        store['profiles'] = raw.get('profiles') or {}
    return store


def _save_store(store: dict) -> None:
    _ensure_store_file()
    _STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding='utf-8')


def list_profiles() -> list[dict]:
    return [deepcopy(_PROFILE_MAP[key]) for key in ['no_feedback_single', 'error_feedback_iter', 'full_chain']]


def get_profile_by_key(profile_key: str | None) -> dict:
    key = str(profile_key or _DEFAULT_KEY).strip()
    if key not in _PROFILE_MAP:
        key = _DEFAULT_KEY
    return deepcopy(_PROFILE_MAP[key])


def get_profile_for_exp(exp_id: int | str) -> dict:
    store = _load_store()
    key = str((store.get('profiles') or {}).get(str(exp_id)) or _DEFAULT_KEY)
    return get_profile_by_key(key)


def save_profile_for_exp(exp_id: int | str, profile_key: str | None) -> dict:
    profile = get_profile_by_key(profile_key)
    store = _load_store()
    store['profiles'][str(exp_id)] = profile['key']
    _save_store(store)
    return deepcopy(profile)


def delete_profile_for_exp(exp_id: int | str) -> None:
    store = _load_store()
    if str(exp_id) in store.get('profiles', {}):
        del store['profiles'][str(exp_id)]
        _save_store(store)
