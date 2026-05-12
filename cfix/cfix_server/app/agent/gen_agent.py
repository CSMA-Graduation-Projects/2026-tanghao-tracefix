from __future__ import annotations

import ast
import operator
from dataclasses import dataclass

from app.core.cfg import settings
from app.llm.base import LLMBase
from app.llm.factory import get_llm_client
from app.llm.prompt import build_case_prompt, build_case_review_prompt, build_gen_bundle_prompt, build_gen_prompt
from app.utils.public_api import extract_required_public_names, missing_required_public_names
from app.utils.case_block import has_assert_line, normalize_comment_lines


@dataclass
class GeneratedBundle:
    code_text: str
    cases: list[dict]
    source: str = 'fallback'
    raw_text: str = ''


class GenAgent:
    """初始生成代理。

    强化点：
    1. 支持只生成代码；
    2. 支持一次返回“代码 + 测试用例”；
    3. 当 bundle JSON 不稳定时，自动退化到“两阶段生成”：先代码，再测试块；
    4. 对 AI 生成测试块增加二次审查，并补一层本地静态 sanity filter，降低错误测试把系统带偏的概率。
    """

    def __init__(self, client=None):
        self.client = client if client is not None else (get_llm_client() if settings.llm_ready else None)
        self.last_source = 'init'
        self.last_error = ''

    def _gen_code_only(self, problem_text: str, scene: str, title: str = '', case_texts: list[str] | None = None) -> tuple[str, str]:
        raw = self.client.chat(
            build_gen_prompt(problem_text=problem_text, scene=scene, title=title, case_texts=case_texts),
            system_prompt='You are a precise Python coding assistant.',
        )
        code_text = self._ensure_syntax_valid_code(problem_text, scene, LLMBase.extract_python_code(raw), title=title)
        return code_text, raw


    def _ensure_public_contract(self, problem_text: str, scene: str, code_text: str, title: str = '') -> str:
        if (scene or 'func').strip().lower() not in {'class', 'file'}:
            return code_text
        missing = missing_required_public_names(problem_text, code_text, scene=scene, title=title)
        if not missing:
            return code_text
        if not self.client:
            raise RuntimeError(f"模型返回的代码缺少必须公开对象：{', '.join(missing)}")
        required = '、'.join(extract_required_public_names(problem_text, scene=scene, title=title))
        prompt = (
            '你是一名 Python 公开 API 契约修复助手。\n'
            '下面代码主体可能基本正确，但缺少题目明确要求的公开对象名。\n'
            '请在保持题意与现有实现尽量一致的前提下，补齐并真正定义这些公开对象，返回完整可运行代码。\n'
            '禁止输出解释说明，禁止输出 Markdown 代码块。\n\n'
            f'任务场景：{scene}\n'
            f'题目要求的公开对象：{required}\n'
            f'当前缺失对象：{", ".join(missing)}\n\n'
            f'题目描述：\n{(problem_text or "").strip()}\n\n'
            f'当前代码：\n{(code_text or "").strip()}\n'
        )
        raw = self.client.chat(prompt, system_prompt='You are a precise Python public API repair assistant.')
        fixed = LLMBase.extract_python_code(raw)
        if fixed.strip() and self._syntax_ok(fixed) and not missing_required_public_names(problem_text, fixed, scene=scene, title=title):
            return fixed
        raise RuntimeError(f"模型返回的代码缺少必须公开对象：{', '.join(missing)}")

    @staticmethod
    def _syntax_ok(code_text: str) -> bool:
        try:
            ast.parse(code_text or '')
            return True
        except Exception:
            return False

    def _ensure_syntax_valid_code(self, problem_text: str, scene: str, code_text: str, title: str = '') -> str:
        cleaned = (code_text or '').strip()
        if not cleaned:
            raise RuntimeError('模型没有返回有效代码')
        if self._syntax_ok(cleaned):
            return self._ensure_public_contract(problem_text, scene, cleaned, title=title)
        repaired = LLMBase.extract_python_code(cleaned)
        if repaired.strip() and self._syntax_ok(repaired):
            return self._ensure_public_contract(problem_text, scene, repaired, title=title)
        if not self.client:
            raise RuntimeError('模型返回的初始代码语法无效')
        prompt = (
            '你是一名 Python 语法修复助手。\n'
            '下面是一段已经基本成型但语法无效的 Python 代码。\n'
            '请在尽量保持原始结构与意图的前提下，只修复语法问题，返回完整可运行代码。\n'
            '禁止输出解释说明，禁止输出 Markdown 代码块。\n\n'
            f'任务场景：{scene}\n\n'
            f'题目描述：\n{(problem_text or "").strip()}\n\n'
            f'当前代码：\n{cleaned}\n'
        )
        raw = self.client.chat(prompt, system_prompt='You are a precise Python syntax repair assistant.')
        fixed = LLMBase.extract_python_code(raw)
        if fixed.strip() and self._syntax_ok(fixed):
            return self._ensure_public_contract(problem_text, scene, fixed, title=title)
        raise RuntimeError('模型返回的初始代码语法无效，且二次语法修复仍失败')

    def _gen_cases_only(self, problem_text: str, scene: str, *, title: str = '', case_cfg: dict | None = None) -> tuple[list[dict], str]:
        raw = self.client.chat(
            build_case_prompt(problem_text=problem_text, scene=scene, title=title, count=int((case_cfg or {}).get('count') or 8), case_cfg=case_cfg or {}),
            system_prompt='You are a precise software testing assistant.',
        )
        try:
            data = LLMBase.extract_json_obj(raw)
            rows = data.get('cases') or []
        except Exception:
            rows = []
        cases = self._normalize_cases(rows)
        if not cases:
            # 兜底：从自由文本里抽取以 assert 开头的块。
            cases = self._extract_cases_from_text(raw)
        return cases, raw

    def _review_cases_only(self, problem_text: str, scene: str, *, title: str = '', cases: list[dict] | None = None) -> tuple[list[dict], str]:
        if not self.client or not cases:
            return list(cases or []), ''
        raw = self.client.chat(
            build_case_review_prompt(problem_text=problem_text, scene=scene, title=title, cases=cases or []),
            system_prompt='You are a precise software testing reviewer.',
        )
        try:
            data = LLMBase.extract_json_obj(raw)
            rows = data.get('cases') or []
        except Exception:
            rows = []
        reviewed = self._normalize_cases(rows)
        return reviewed, raw

    @staticmethod
    def _needs_two_stage(code_text: str, cases: list[dict]) -> bool:
        if not code_text.strip():
            return True
        if LLMBase.looks_like_bundle_contaminated_code(code_text):
            return True
        if not cases:
            return True
        return False

    def _gen_bundle_or_fallback(self, problem_text: str, scene: str, *, title: str = '', case_cfg: dict | None = None, case_texts: list[str] | None = None) -> GeneratedBundle:
        raw = self.client.chat(
            build_gen_bundle_prompt(problem_text=problem_text, scene=scene, title=title, case_cfg=case_cfg or {}, case_texts=case_texts),
            system_prompt='You are a precise Python coding assistant.',
        )

        code_text = ''
        cases: list[dict] = []
        bundle_ok = False

        try:
            data = LLMBase.extract_json_obj(raw)
            code_text = self._ensure_syntax_valid_code(problem_text, scene, LLMBase.extract_python_code(str(data.get('code') or '')))
            cases = self._normalize_cases(data.get('cases') or [])
            bundle_ok = bool(code_text.strip() and cases)
        except Exception:
            code_text = LLMBase.extract_python_code(raw)
            cases = []
            bundle_ok = False

        if bundle_ok and not self._needs_two_stage(code_text, cases):
            reviewed_cases = self._post_process_cases(problem_text, scene, title=title, cases=cases)
            return GeneratedBundle(code_text=code_text, cases=reviewed_cases, source='llm_bundle_reviewed', raw_text=raw)

        # bundle 不稳时，不再直接拿混杂 raw 当最终代码，而是退化到“两阶段生成”。
        # 这样可以避免把 JSON 里的 cases 尾巴写进代码版本，也能保证 AI 生成用例真正落到测试区。
        if not code_text.strip() or LLMBase.looks_like_bundle_contaminated_code(code_text):
            code_text, _code_raw = self._gen_code_only(problem_text, scene, title=title, case_texts=case_texts)

        try:
            cases, _case_raw = self._gen_cases_only(problem_text, scene, title=title, case_cfg=case_cfg or {})
        except Exception:
            cases = self._extract_cases_from_text(raw)
            if not cases and settings.llm_strict:
                raise

        reviewed_cases = self._post_process_cases(problem_text, scene, title=title, cases=cases)
        return GeneratedBundle(code_text=code_text, cases=reviewed_cases, source='llm_two_stage_reviewed', raw_text=raw)

    def run(self, problem_text: str, scene: str = 'func', *, title: str = '', auto_gen_cases: bool = False, case_cfg: dict | None = None, case_texts: list[str] | None = None) -> GeneratedBundle:
        if self.client:
            try:
                if auto_gen_cases:
                    bundle = self._gen_bundle_or_fallback(problem_text, scene, title=title, case_cfg=case_cfg or {}, case_texts=case_texts)
                    self.last_source = bundle.source
                    self.last_error = '' if bundle.cases else 'case_generation_fallback'
                    return bundle

                code_text, raw = self._gen_code_only(problem_text, scene, title=title, case_texts=case_texts)
                self.last_source = 'llm'
                self.last_error = ''
                return GeneratedBundle(code_text=code_text, cases=[], source='llm', raw_text=raw)
            except Exception as exc:  # noqa: BLE001
                self.last_source = 'fallback'
                self.last_error = str(exc)
                if settings.llm_strict:
                    raise RuntimeError(f'GenAgent 真实模型生成失败：{exc}') from exc

        fallback = self._fallback_code(problem_text=problem_text, scene=scene)
        cases = self._fallback_cases(scene=scene, case_cfg=case_cfg or {}) if auto_gen_cases else []
        return GeneratedBundle(code_text=fallback, cases=cases, source='fallback', raw_text='')

    @staticmethod
    def _has_assert(text: str) -> bool:
        return has_assert_line(text)

    @classmethod
    def _extract_cases_from_text(cls, raw: str) -> list[dict]:
        text = normalize_comment_lines(str(raw or '')).replace('\r\n', '\n').strip()
        if not text:
            return []
        blocks = [x.strip('\n') for x in text.split('\n\n') if x.strip()]
        items: list[dict] = []
        for idx, block in enumerate(blocks, start=1):
            if not cls._has_assert(block):
                continue
            items.append({
                'src_type': 'ai_block',
                'case_in': None,
                'expect_out': None,
                'assert_text': block.strip(),
                'weight': 1.0,
                'sort_no': idx,
            })
        return items

    @classmethod
    def _normalize_cases(cls, rows: list) -> list[dict]:
        items: list[dict] = []
        for idx, row in enumerate(rows, start=1):
            if isinstance(row, dict):
                text = normalize_comment_lines(str(row.get('assert_text') or '')).strip('\n')
                src_type = str(row.get('src_type') or '').strip()
            else:
                text = normalize_comment_lines(str(row or '')).strip('\n')
                src_type = ''
            if not text.strip():
                continue
            if not src_type:
                src_type = 'ai_block' if cls._has_assert(text) else 'setup'
            items.append({
                'src_type': src_type,
                'case_in': None,
                'expect_out': None,
                'assert_text': text.strip(),
                'weight': 1.0,
                'sort_no': idx,
            })
        return items

    def _post_process_cases(self, problem_text: str, scene: str, *, title: str = '', cases: list[dict]) -> list[dict]:
        base = self._dedupe_cases(self._normalize_cases(cases))
        if not base:
            return []
        reviewed = base
        if self.client:
            try:
                llm_reviewed, _review_raw = self._review_cases_only(problem_text, scene, title=title, cases=base)
                llm_reviewed = self._dedupe_cases(self._normalize_cases(llm_reviewed))
                if llm_reviewed:
                    reviewed = llm_reviewed
            except Exception:
                # 审查失败不阻塞主链路，继续走本地 sanity filter。
                pass
        filtered = self._static_sanity_filter_cases(problem_text, scene, reviewed)
        return filtered or reviewed

    @staticmethod
    def _dedupe_cases(cases: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for item in cases or []:
            text = normalize_comment_lines(str((item or {}).get('assert_text') or '')).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            row = dict(item)
            row['assert_text'] = text
            row['sort_no'] = len(out) + 1
            out.append(row)
        return out

    _BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    _UNARY_OPS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    @classmethod
    def _safe_eval_expr(cls, node: ast.AST):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.List):
            return [cls._safe_eval_expr(elt) for elt in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(cls._safe_eval_expr(elt) for elt in node.elts)
        if isinstance(node, ast.Set):
            return {cls._safe_eval_expr(elt) for elt in node.elts}
        if isinstance(node, ast.Dict):
            return {cls._safe_eval_expr(k): cls._safe_eval_expr(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.UnaryOp) and type(node.op) in cls._UNARY_OPS:
            return cls._UNARY_OPS[type(node.op)](cls._safe_eval_expr(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in cls._BIN_OPS:
            return cls._BIN_OPS[type(node.op)](cls._safe_eval_expr(node.left), cls._safe_eval_expr(node.right))
        raise ValueError(f'unsupported_expr: {type(node).__name__}')

    @classmethod
    def _literal_matrix(cls, node: ast.AST):
        try:
            value = cls._safe_eval_expr(node)
        except Exception:
            return None
        if not isinstance(value, list):
            return None
        if not all(isinstance(row, list) for row in value):
            return None
        return value

    @staticmethod
    def _matrix_max_value(matrix: list[list]):
        flat = [x for row in matrix for x in row]
        if not flat:
            return None
        return max(flat)

    @staticmethod
    def _matrix_row_sum(matrix: list[list], idx: int):
        if idx < 0 or idx >= len(matrix):
            return 0
        return sum(matrix[idx])

    @staticmethod
    def _matrix_col_sum(matrix: list[list], idx: int):
        if idx < 0:
            return 0
        total = 0
        for row in matrix:
            if idx < len(row):
                total += row[idx]
        return total

    @classmethod
    def _matrixbox_case_consistent(cls, problem_text: str, case_text: str) -> bool:
        low = (problem_text or '').lower()
        if 'row_sum' not in low or 'col_sum' not in low or 'max_value' not in low:
            return True
        try:
            tree = ast.parse(case_text)
        except Exception:
            return True

        env: dict[str, list[list]] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if isinstance(node.value, ast.Call) and getattr(node.value.func, 'id', None) == 'MatrixBox' and node.value.args:
                    matrix = cls._literal_matrix(node.value.args[0])
                    if matrix is not None:
                        env[name] = matrix

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assert):
                continue
            test = node.test
            if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
                continue
            op = test.ops[0]
            if not isinstance(op, (ast.Eq, ast.Is)):
                continue
            call = test.left
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name):
                continue
            obj_name = call.func.value.id
            if obj_name not in env:
                continue
            matrix = env[obj_name]
            method = call.func.attr
            try:
                expected = cls._safe_eval_expr(test.comparators[0])
            except Exception:
                continue
            supported = False
            actual = None
            if method == 'max_value' and not call.args:
                supported = True
                actual = cls._matrix_max_value(matrix)
            elif method == 'row_sum' and len(call.args) == 1:
                try:
                    idx = cls._safe_eval_expr(call.args[0])
                except Exception:
                    continue
                if isinstance(idx, int):
                    supported = True
                    actual = cls._matrix_row_sum(matrix, idx)
            elif method == 'col_sum' and len(call.args) == 1:
                try:
                    idx = cls._safe_eval_expr(call.args[0])
                except Exception:
                    continue
                if isinstance(idx, int):
                    supported = True
                    actual = cls._matrix_col_sum(matrix, idx)
            if supported and actual != expected:
                return False
        return True

    @classmethod
    def _static_sanity_filter_cases(cls, problem_text: str, scene: str, cases: list[dict]) -> list[dict]:
        scene = (scene or 'func').strip().lower()
        if scene != 'class':
            return cls._dedupe_cases(cases)
        out: list[dict] = []
        for item in cases or []:
            text = normalize_comment_lines(str((item or {}).get('assert_text') or '')).strip()
            if not text:
                continue
            if not cls._matrixbox_case_consistent(problem_text, text):
                continue
            row = dict(item)
            row['sort_no'] = len(out) + 1
            out.append(row)
        return cls._dedupe_cases(out)

    @staticmethod
    def _fallback_code(problem_text: str, scene: str) -> str:
        scene = (scene or 'func').strip().lower()
        if scene == 'class':
            return (
                'class Solution:\n'
                '    def __init__(self, *args, **kwargs):\n'
                '        pass\n'
            )
        if scene == 'file':
            return (
                '"""AUTO_GENERATED_MODULE"""\n\n'
                'def main():\n'
                '    raise NotImplementedError("请根据题目补全模块公开 API")\n\n'
                'if __name__ == "__main__":\n'
                '    main()\n'
            )
        return (
            'def solve(*args, **kwargs):\n'
            '    """AUTO_GENERATED_FALLBACK"""\n'
            '    raise NotImplementedError("请根据题目补全 solve 逻辑")\n'
        )

    @staticmethod
    def _fallback_cases(scene: str, case_cfg: dict) -> list[dict]:
        count = max(4, min(int(case_cfg.get('count') or 8), 30))
        scene = (scene or 'func').strip().lower()
        base = {
            'func': [
                'assert solve(0) is not None',
                'assert solve(1) is not None',
                'assert solve(-1) is not None',
                'assert solve(10) is not None',
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
        rows = base.get(scene, base['func'])
        items = []
        for idx, text in enumerate(rows[:count], start=1):
            items.append({
                'src_type': 'ai_block' if GenAgent._has_assert(text) else 'setup',
                'case_in': None,
                'expect_out': None,
                'assert_text': text,
                'weight': 1.0,
                'sort_no': idx,
            })
        return items
