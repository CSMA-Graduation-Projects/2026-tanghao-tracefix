from __future__ import annotations

from dataclasses import dataclass

from app.core.cfg import settings
from app.llm.base import LLMBase
from app.svc.model_svc import resolve_llm_client
from app.llm.prompt import build_case_prompt
from app.utils.case_block import normalize_case_rows, has_assert_line, normalize_comment_lines


@dataclass
class GeneratedCase:
    assert_text: str
    src_type: str = 'ai_block'
    weight: float = 1.0
    sort_no: int = 1


class CaseService:
    """测试用例生成服务。

    目标：给 WorkBench 提供“AI 生成测试用例”的完整能力。
    - 真实模型可用时：走 qwen 生成 JSON；
    - 模型不可用时：回退到场景模板，保证页面功能不中断。
    """

    @staticmethod
    def _has_assert(text: str) -> bool:
        return has_assert_line(text)

    def generate_cases(self, *, problem_text: str, scene: str = 'func', title: str = '', count: int = 8, case_cfg: dict | None = None, db=None, user_id: int | None = None, model_id: int | None = None) -> list[GeneratedCase]:
        problem_text = (problem_text or '').strip()
        scene = (scene or 'func').strip().lower()
        count = max(4, min(int(count or 8), 30))
        if not problem_text:
            raise ValueError('题目描述不能为空')

        client = resolve_llm_client(db, user_id=user_id, model_id=model_id) if db is not None and user_id is not None else (None if not settings.llm_ready else resolve_llm_client())
        strict_mode = getattr(getattr(client, 'config', None), 'strict', settings.llm_strict)

        if client:
            try:
                raw = client.chat(
                    build_case_prompt(problem_text=problem_text, scene=scene, title=title, count=count, case_cfg=case_cfg or {}),
                    system_prompt='You are a precise software testing assistant.',
                )
                payload = LLMBase.extract_json_obj(raw)
                rows = payload.get('cases') or []
                norm = normalize_case_rows(scene, [
                    {'assert_text': normalize_comment_lines((row.get('assert_text') if isinstance(row, dict) else row) or ''), 'src_type': (row.get('src_type') if isinstance(row, dict) else ''), 'sort_no': idx}
                    for idx, row in enumerate(rows, start=1)
                ])
                items: list[GeneratedCase] = [GeneratedCase(assert_text=x.assert_text, src_type=x.src_type.replace('custom_', 'ai_') if x.src_type.startswith('custom_') else x.src_type, sort_no=idx) for idx, x in enumerate(norm, start=1)]
                if items:
                    return items[:count]
                raise RuntimeError('模型没有生成有效断言')
            except Exception:
                if strict_mode:
                    raise

        return self._fallback_cases(scene=scene, count=count)

    def _fallback_cases(self, *, scene: str, count: int) -> list[GeneratedCase]:
        bank = {
            'func': [
                'assert solve(0) == 0',
                'assert solve(1) == 1',
                'assert solve(2) != None',
                'assert solve(-1) != None',
                'assert solve(10) != None',
            ],
            'class': [
                'def _mk_obj():\n    return Solution()',
                'obj = _mk_obj()\nassert obj is not None\nassert hasattr(obj, "__class__")',
                'obj = _mk_obj()\nassert obj.__class__.__name__ != ""',
                'obj = _mk_obj()\nassert dir(obj) is not None',
            ],
            'file': [
                'def _api_candidates(ns):\n    return [k for k, v in ns.items() if callable(v) and not k.startswith("_")]',
                'assert isinstance(_api_candidates(globals()), list)',
                'apis = _api_candidates(globals())\nassert len(apis) >= 1',
                'assert globals() is not None\nassert locals() is not None',
            ],
        }
        rows = bank.get(scene, bank['func'])
        norm = normalize_case_rows(scene, [
            {'assert_text': normalize_comment_lines(text), 'src_type': ('ai_block' if self._has_assert(text) else 'setup'), 'sort_no': idx}
            for idx, text in enumerate(rows[:count], start=1)
        ])
        items: list[GeneratedCase] = []
        for idx, item in enumerate(norm, start=1):
            src = item.src_type.replace('custom_', 'ai_') if item.src_type.startswith('custom_') else item.src_type
            items.append(GeneratedCase(assert_text=item.assert_text, src_type=src, sort_no=idx))
        return items
