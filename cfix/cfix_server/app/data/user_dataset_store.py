from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from app.data.bench_bank import (
    _DATASET_CANONICAL,
    _canonical_dataset_name,
    get_dataset_meta,
    get_dataset_names,
    get_exp_problems,
    get_dataset_size,
)

_STORE_PATH = Path(__file__).resolve().parent / 'user_datasets.json'
_NAME_RE = re.compile(r'^[a-z][a-z0-9_]{1,31}$')


def _default_store() -> dict:
    return {
        'datasets': {},
        'builtin_overrides': {},
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
    if isinstance(raw, dict):
        store['datasets'] = raw.get('datasets') if isinstance(raw.get('datasets'), dict) else {}
        store['builtin_overrides'] = raw.get('builtin_overrides') if isinstance(raw.get('builtin_overrides'), dict) else {}
    return store


def _save_store(store: dict) -> None:
    _ensure_store_file()
    _STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding='utf-8')


def _normalize_case(case: dict, sort_no: int) -> dict:
    return {
        'src_type': str(case.get('src_type') or 'dataset').strip() or 'dataset',
        'case_in': case.get('case_in'),
        'expect_out': case.get('expect_out'),
        'assert_text': str(case.get('assert_text') or '').rstrip(),
        'weight': float(case.get('weight') or 1.0),
        'sort_no': int(case.get('sort_no') or sort_no),
    }


def _normalize_item(item: dict, *, fallback_id: str | None = None, builtin: bool = False, dataset_name: str | None = None) -> dict:
    title = str(item.get('title') or '').strip()
    problem_text = str(item.get('problem_text') or '').strip()
    if not title:
        raise ValueError('测试任务标题不能为空')
    if not problem_text:
        raise ValueError('题目描述不能为空')
    scene = str(item.get('scene') or 'func').strip().lower()
    if scene not in {'func', 'class', 'file'}:
        raise ValueError('任务场景仅支持 func / class / file')

    raw_cases = item.get('cases') or []
    if not isinstance(raw_cases, list):
        raise ValueError('测试用例必须为列表')
    cases = []
    for idx, case in enumerate(raw_cases, start=1):
        if not isinstance(case, dict):
            raise ValueError('测试用例格式不正确')
        norm_case = _normalize_case(case, idx)
        if not norm_case['assert_text']:
            raise ValueError('测试用例内容不能为空')
        cases.append(norm_case)

    item_id = str(item.get('id') or fallback_id or uuid4().hex[:12]).strip()
    data = {
        'id': item_id,
        'title': title,
        'scene': scene,
        'problem_text': problem_text,
        'cases': cases,
        'case_count': len(cases),
        'builtin': bool(builtin),
    }
    if dataset_name:
        data['dataset'] = dataset_name
    if 'source_idx' in item and item.get('source_idx') is not None:
        data['source_idx'] = int(item.get('source_idx'))
    return data


def _dataset_items_from_builtin(name: str) -> list[dict]:
    canonical = _canonical_dataset_name(name)
    rows = []
    for base in get_exp_problems(canonical, get_dataset_size(canonical)):
        item = _normalize_item(
            {
                'id': f'builtin-{base.get("source_idx")}',
                'source_idx': int(base.get('source_idx') or 0),
                'title': base.get('title'),
                'scene': base.get('scene'),
                'problem_text': base.get('problem_text'),
                'cases': deepcopy(base.get('cases') or []),
            },
            builtin=True,
            dataset_name=canonical,
        )
        rows.append(item)
    return rows


def _apply_builtin_overrides(name: str, rows: list[dict], store: dict) -> list[dict]:
    canonical = _canonical_dataset_name(name)
    override = store.get('builtin_overrides', {}).get(canonical) or {}
    deleted = {str(x) for x in (override.get('deleted') or [])}
    item_override = override.get('items') or {}
    merged: list[dict] = []
    for item in rows:
        src_idx = str(item.get('source_idx') or '')
        if src_idx and src_idx in deleted:
            continue
        current = deepcopy(item)
        extra = item_override.get(src_idx)
        if isinstance(extra, dict):
            extra_copy = deepcopy(extra)
            extra_copy['id'] = current['id']
            extra_copy['source_idx'] = current.get('source_idx')
            current = _normalize_item(extra_copy, fallback_id=current['id'], builtin=True, dataset_name=canonical)
        merged.append(current)
    return merged


def list_dataset_names_all() -> list[str]:
    store = _load_store()
    builtin = list(get_dataset_names())
    custom = sorted([k for k in store.get('datasets', {}).keys() if k not in _DATASET_CANONICAL])
    return builtin + custom


def list_dataset_meta_all() -> list[dict]:
    names = list_dataset_names_all()
    return [get_dataset_meta_ext(name) for name in names]


def get_dataset_meta_ext(name: str) -> dict:
    store = _load_store()
    if name in _DATASET_CANONICAL or name in sum([v.get('aliases', []) for v in _DATASET_CANONICAL.values()], []):
        canonical = _canonical_dataset_name(name)
        meta = get_dataset_meta(canonical)
        meta['builtin'] = True
        meta['editable'] = False
        meta['deletable'] = False
        meta['size'] = len(list_dataset_items(canonical, store=store))
        return meta

    data = store.get('datasets', {}).get(name)
    if not isinstance(data, dict):
        raise KeyError(f'数据集不存在：{name}')
    items = data.get('items') if isinstance(data.get('items'), list) else []
    return {
        'name': name,
        'display_name': str(data.get('display_name') or name),
        'desc': str(data.get('desc') or ''),
        'size': len(items),
        'aliases': [],
        'input_name': name,
        'alias_of': None,
        'builtin': False,
        'editable': True,
        'deletable': True,
    }


def list_dataset_items(name: str, *, store: dict | None = None) -> list[dict]:
    current = store or _load_store()
    if name in _DATASET_CANONICAL or name in sum([v.get('aliases', []) for v in _DATASET_CANONICAL.values()], []):
        base = _dataset_items_from_builtin(name)
        return _apply_builtin_overrides(name, base, current)

    data = current.get('datasets', {}).get(name)
    if not isinstance(data, dict):
        raise KeyError(f'数据集不存在：{name}')
    rows = []
    for item in data.get('items') or []:
        if isinstance(item, dict):
            rows.append(_normalize_item(item, fallback_id=str(item.get('id') or uuid4().hex[:12]), builtin=False, dataset_name=name))
    return rows


def get_dataset_item(name: str, item_id: str) -> dict:
    for item in list_dataset_items(name):
        if str(item.get('id')) == str(item_id):
            return item
    raise KeyError('测试任务不存在')


def create_dataset(name: str, display_name: str, desc: str = '', initial_item: dict | None = None) -> dict:
    key = str(name or '').strip().lower()
    if not _NAME_RE.match(key):
        raise ValueError('数据集标识需使用小写字母开头，仅支持小写字母、数字和下划线，长度 2~32')
    if key in _DATASET_CANONICAL or key in sum([v.get('aliases', []) for v in _DATASET_CANONICAL.values()], []):
        raise ValueError('该名称与内置数据集冲突，请更换')
    store = _load_store()
    if key in store.get('datasets', {}):
        raise ValueError('数据集已存在')
    payload = {
        'name': key,
        'display_name': str(display_name or key).strip() or key,
        'desc': str(desc or '').strip(),
        'items': [],
    }
    if initial_item:
        payload['items'].append(_normalize_item(initial_item, builtin=False, dataset_name=key))
    store['datasets'][key] = payload
    _save_store(store)
    return get_dataset_meta_ext(key)


def delete_dataset(name: str) -> None:
    if name in _DATASET_CANONICAL:
        raise ValueError('内置数据集不支持删除')
    store = _load_store()
    if name not in store.get('datasets', {}):
        raise KeyError('数据集不存在')
    del store['datasets'][name]
    _save_store(store)


def create_dataset_item(name: str, payload: dict) -> dict:
    store = _load_store()
    if name in _DATASET_CANONICAL:
        raise ValueError('内置数据集不支持新增测试任务，请先创建自定义数据集')
    ds = store.get('datasets', {}).get(name)
    if not isinstance(ds, dict):
        raise KeyError('数据集不存在')
    item = _normalize_item(payload, builtin=False, dataset_name=name)
    items = ds.get('items') if isinstance(ds.get('items'), list) else []
    items.append(item)
    ds['items'] = items
    store['datasets'][name] = ds
    _save_store(store)
    return item


def update_dataset_item(name: str, item_id: str, payload: dict) -> dict:
    store = _load_store()
    if name in _DATASET_CANONICAL:
        source_idx: str | None = None
        for item in list_dataset_items(name, store=store):
            if str(item.get('id')) == str(item_id):
                source_idx = str(item.get('source_idx') or '')
                break
        if not source_idx:
            raise KeyError('测试任务不存在')
        override_root = store.setdefault('builtin_overrides', {}).setdefault(name, {'deleted': [], 'items': {}})
        deleted = [str(x) for x in (override_root.get('deleted') or []) if str(x) != source_idx]
        override_root['deleted'] = deleted
        merged = _normalize_item({**payload, 'source_idx': int(source_idx)}, fallback_id=item_id, builtin=True, dataset_name=name)
        override_root.setdefault('items', {})[source_idx] = {
            'title': merged['title'],
            'scene': merged['scene'],
            'problem_text': merged['problem_text'],
            'cases': merged['cases'],
        }
        _save_store(store)
        return merged

    ds = store.get('datasets', {}).get(name)
    if not isinstance(ds, dict):
        raise KeyError('数据集不存在')
    items = ds.get('items') if isinstance(ds.get('items'), list) else []
    found = False
    new_items = []
    updated = None
    for item in items:
        if str(item.get('id')) == str(item_id):
            updated = _normalize_item({**payload, 'id': item_id}, fallback_id=item_id, builtin=False, dataset_name=name)
            new_items.append(updated)
            found = True
        else:
            new_items.append(item)
    if not found:
        raise KeyError('测试任务不存在')
    ds['items'] = new_items
    store['datasets'][name] = ds
    _save_store(store)
    return updated


def delete_dataset_item(name: str, item_id: str) -> None:
    store = _load_store()
    if name in _DATASET_CANONICAL:
        target = None
        for item in list_dataset_items(name, store=store):
            if str(item.get('id')) == str(item_id):
                target = str(item.get('source_idx') or '')
                break
        if not target:
            raise KeyError('测试任务不存在')
        override_root = store.setdefault('builtin_overrides', {}).setdefault(name, {'deleted': [], 'items': {}})
        deleted = {str(x) for x in (override_root.get('deleted') or [])}
        deleted.add(target)
        override_root['deleted'] = sorted(deleted, key=lambda x: int(x) if str(x).isdigit() else x)
        if isinstance(override_root.get('items'), dict):
            override_root['items'].pop(target, None)
        _save_store(store)
        return

    ds = store.get('datasets', {}).get(name)
    if not isinstance(ds, dict):
        raise KeyError('数据集不存在')
    items = ds.get('items') if isinstance(ds.get('items'), list) else []
    new_items = [item for item in items if str(item.get('id')) != str(item_id)]
    if len(new_items) == len(items):
        raise KeyError('测试任务不存在')
    ds['items'] = new_items
    store['datasets'][name] = ds
    _save_store(store)
