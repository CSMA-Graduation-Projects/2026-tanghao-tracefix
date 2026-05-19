"""修复代理封装，负责承接对应阶段的大模型调用。"""

from __future__ import annotations

import ast
import re
from app.core.cfg import settings
from app.llm.base import LLMBase
from app.llm.factory import get_llm_client
from app.llm.prompt import build_fix_prompt
from app.utils.fail_focus import build_file_fix_guard, build_file_joint_hypothesis, parse_lesson_stats
from app.utils.public_api import extract_required_public_names, missing_required_public_names
from app.utils.api_contract import build_case_contract_guard


class FixAgent:
    """修复代理。

    这一版不再只做“失败即直接塞给模型”的单步修补，而是补了三层稳健控制：
    1. file 级复杂任务在共享契约反复失败时，会自动进入“模块级稳健重构模式”；
    2. 模型返回后先做 Python 语法校验；
    3. 对明显把测试内容抄进代码的结果做拦截，避免只为过当前测试块硬编码。
    """

    def __init__(self, client=None):
        self.client = client if client is not None else (get_llm_client() if settings.llm_ready else None)
        self.last_source = "init"
        self.last_error = ""


    def _repair_missing_public_names(self, problem_text: str, scene: str, code_text: str, missing: list[str], title: str = '', case_texts: list[str] | None = None) -> str:
        if not self.client:
            raise RuntimeError(f"模型返回代码缺少必须公开对象：{', '.join(missing)}")
        required = '、'.join(extract_required_public_names(problem_text, scene=scene, title=title))
        contract_guard = build_case_contract_guard('TypeError', case_texts, scene=scene)
        prompt = (
            '你是一名 Python 模块公开 API 契约修复助手。\n'
            '请在保持代码原有题意与主要逻辑尽量不变的前提下，补齐题目明确要求但当前缺失的公开对象。\n'
            '返回完整可运行代码，不要输出解释说明，不要输出 Markdown 代码块。\n\n'
            f'任务场景：{scene}\n'
            f'题目要求的公开对象：{required}\n'
            f'当前缺失对象：{", ".join(missing)}\n\n'
            f'题目描述：\n{(problem_text or "").strip()}\n\n'
            f'当前代码：\n{(code_text or "").strip()}\n'
        )
        raw = self.client.chat(prompt, system_prompt='You are a precise Python public API repair assistant.')
        fixed = LLMBase.extract_python_code(raw)
        ok, _err = self._syntax_ok(fixed)
        if fixed.strip() and ok and not self._contains_test_artifacts(fixed) and not missing_required_public_names(problem_text, fixed, scene=scene, title=title):
            return fixed
        raise RuntimeError(f"模型返回代码缺少必须公开对象：{', '.join(missing)}")

    @staticmethod
    def _syntax_ok(code: str) -> tuple[bool, str]:
        try:
            ast.parse(code or '')
            return True, ''
        except SyntaxError as exc:  # noqa: BLE001
            return False, f'SyntaxError: {exc}'

    @staticmethod
    def _contains_test_artifacts(code: str) -> bool:
        src = code or ''
        low = src.lower()
        if 'auto_fix_note' in low:
            return True
        markers = [
            'assert ', 'assert_raises(', 'case#', 'cfg2 =', 'cfg3 =', 'cfg4 =', 'cfg5 =', 'cfg6 =', 'cfg7 =', 'cfg8 =', 'cfg9 =',
            'ops9 =', 'res9 =', 'bus7', 'bus8', 'r81', 'r82',
        ]
        return any(m in low for m in markers)



    @staticmethod
    def _target_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
        names: list[str] = []
        targets = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets or [])
        elif isinstance(node, ast.AnnAssign) and node.target is not None:
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.append(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        names.append(elt.id)
        return names

    @classmethod
    def _looks_like_demo_assign(cls, node: ast.Assign | ast.AnnAssign) -> bool:
        names = cls._target_names(node)
        if not names:
            return False
        suspicious_prefixes = (
            'cfg', 'bus', 'res', 'ops', 'case', 'task', 'graph', 'engine', 'once', 'bad', 'ok', 'tok', 'rt', 'g', 'r'
        )
        if any(name.isupper() or name.startswith('__') for name in names):
            return False
        for name in names:
            low = name.lower()
            if re.fullmatch(r'r\d+', low):
                return True
            if re.fullmatch(r'(cfg|bus|res|ops|case|task|graph)\d+', low):
                return True
            if any(low.startswith(prefix) for prefix in suspicious_prefixes):
                return True
        return False

    @classmethod
    def _strip_obvious_test_tail(cls, code: str) -> str:
        src = (code or '').strip()
        if not src:
            return ''
        try:
            tree = ast.parse(src)
        except Exception:
            return src

        lines = src.splitlines()
        keep_until = 0
        saw_api_body = False
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(getattr(node, 'value', None), ast.Constant) and isinstance(node.value.value, str):
                keep_until = max(keep_until, int(getattr(node, 'end_lineno', node.lineno) or node.lineno))
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                saw_api_body = True
                keep_until = max(keep_until, int(getattr(node, 'end_lineno', node.lineno) or node.lineno))
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                if cls._looks_like_demo_assign(node):
                    break
                keep_until = max(keep_until, int(getattr(node, 'end_lineno', node.lineno) or node.lineno))
                continue
            if isinstance(node, ast.If):
                test = getattr(node, 'test', None)
                if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == '__name__':
                    break
            if saw_api_body and isinstance(node, (ast.Assert, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Match, ast.Try, ast.Expr)):
                break
            keep_until = max(keep_until, int(getattr(node, 'end_lineno', node.lineno) or node.lineno))

        if keep_until <= 0:
            return src
        trimmed = '\n'.join(lines[:keep_until]).strip()
        return trimmed or src

    @classmethod
    def _salvage_fix_response(cls, raw: str) -> str:
        candidate = LLMBase.extract_python_code(raw)
        if not candidate.strip():
            return ''
        attempts = [candidate]
        trimmed = cls._strip_obvious_test_tail(candidate)
        if trimmed and trimmed not in attempts:
            attempts.append(trimmed)
        for item in attempts:
            ok, _err = cls._syntax_ok(item)
            if ok and not cls._contains_test_artifacts(item):
                return item
        return ''

    @staticmethod
    def _need_rebuild_mode(err_text: str = '', lesson_text: str = '', scene: str = 'func') -> bool:
        """是否进入更激进的“模块级重建”模式。

        触发条件不依赖单条报错，而是看：
        1. file 级任务是否出现共享契约/共享 helper 类失败；
        2. recent lesson 是否已表现出停滞、振荡、重复 case；
        3. 当前错误是否明显属于“继续微调单个 if 不会收敛”的场景。
        """
        if (scene or 'func').strip().lower() != 'file':
            return False

        low = ((err_text or '') + '\n' + (lesson_text or '')).lower()
        lesson_info = parse_lesson_stats(lesson_text)
        repeated_case_ids = lesson_info.get('repeated_case_ids', [])
        repeated_strategies = lesson_info.get('repeated_strategies', [])

        scopedconfig_like = any(k in low for k in (
            'scopedconfig', 'effective_items', 'itemsr', 'getr', 'render(', 'resolve=true',
            'batch_apply', '${host}', '${port}', '$$', '循环引用', 'recursionerror',
        ))
        shared_contract = any(k in low for k in (
            'module_api_contract', '共享 resolver', '共享 helper', '共享契约', '公共逻辑',
        ))
        repeated_failures = len(repeated_case_ids) >= 2 or bool(repeated_strategies)
        stagnated = bool(lesson_info.get('stagnation') or lesson_info.get('oscillation'))
        repeated_timeout = low.count('timeout') >= 2 or low.count('container execution timeout') >= 2
        recursion_contract_split = 'recursionerror' in low and ('valueerror' in low or '循环引用' in low)
        joint_hypothesis = bool(build_file_joint_hypothesis(err_text, lesson_text).strip())

        # 对 ScopedConfig / file 级共享契约类任务，停滞 + 共享逻辑失败时直接进入重建。
        if scopedconfig_like and (stagnated or repeated_failures) and (shared_contract or joint_hypothesis or recursion_contract_split):
            return True

        # 更通用的 file 级任务：一旦出现“多轮不提升 + 共享契约/公共逻辑失败”，避免继续局部补丁。
        if (stagnated or repeated_failures) and (shared_contract or joint_hypothesis or repeated_timeout):
            return True

        return False

    @staticmethod
    def _need_robust_mode(err_text: str = '', lesson_text: str = '', scene: str = 'func') -> bool:
        if (scene or 'func').strip().lower() != 'file':
            return False
        low = ((err_text or '') + '\n' + (lesson_text or '')).lower()
        lesson_info = parse_lesson_stats(lesson_text)
        scoped_like = any(k in low for k in (
            'scopedconfig', 'effective_items', 'itemsr', 'getr', 'render(', 'resolve=true', 'batch_apply', '${host}', '${port}', '$$',
        ))
        shared_contract = 'module_api_contract' in low or '共享 resolver' in low or '共享契约' in low
        repeated_timeout = low.count('timeout') >= 2 or low.count('container execution timeout') >= 2
        repeated_cases = len(lesson_info.get('repeated_case_ids', [])) >= 2
        return scoped_like or shared_contract or repeated_timeout or repeated_cases or lesson_info.get('stagnation') or lesson_info.get('oscillation')

    def _chat_fix(self, *, prompt: str, problem_text: str, scene: str, robust_mode: bool = False, title: str = '', case_texts: list[str] | None = None) -> str:
        raw = self.client.chat(
            prompt,
            system_prompt=(
                'You are a code repair assistant. Prioritize robust, general fixes over test-specific patches.'
                if robust_mode else
                'You are a code repair assistant.'
            ),
        )
        fixed = LLMBase.extract_python_code(raw)
        if not fixed.strip():
            salvaged = self._salvage_fix_response(raw)
            if salvaged:
                return salvaged
            raise RuntimeError('模型返回了空修复代码')
        ok, err = self._syntax_ok(fixed)
        if not ok or self._contains_test_artifacts(fixed):
            salvaged = self._salvage_fix_response(raw)
            if salvaged:
                fixed = salvaged
                ok, err = self._syntax_ok(fixed)
            else:
                if not ok:
                    raise RuntimeError(f'模型返回的修复代码语法无效：{err}')
                raise RuntimeError('模型返回内容疑似夹带测试块或 case 特判，已拒绝该结果')
        if (scene or 'func').strip().lower() in {'class', 'file'}:
            missing = missing_required_public_names(problem_text, fixed, scene=scene, title=title)
            if missing:
                return self._repair_missing_public_names(problem_text, scene, fixed, missing, title=title, case_texts=case_texts)
        return fixed

    def run(
        self,
        problem_text: str,
        code_text: str,
        fix_plan: str,
        err_text: str = "",
        trace_sum: str = "",
        lesson_text: str = "",
        scene: str = "func",
        title: str = '',
        case_texts: list[str] | None = None,
    ) -> str:
        if self.client:
            robust_mode = self._need_robust_mode(err_text=err_text, lesson_text=lesson_text, scene=scene)
            rebuild_mode = self._need_rebuild_mode(err_text=err_text, lesson_text=lesson_text, scene=scene)
            guarded_plan = fix_plan
            if (scene or 'func').strip().lower() == 'file':
                fix_guard = build_file_fix_guard(err_text, lesson_text)
                if fix_guard:
                    guarded_plan = (fix_plan or '').strip() + ('\n\n[FILE_FIX_GUARD]\n' + fix_guard if (fix_plan or '').strip() else fix_guard)
            prompt_order: list[tuple[str, bool, str]] = []
            if rebuild_mode:
                prompt_order.append((
                    build_fix_prompt(
                        problem_text=problem_text,
                        code_text=code_text,
                        err_text=err_text,
                        trace_sum=trace_sum,
                        lesson_text=lesson_text,
                        fix_plan=guarded_plan,
                        scene=scene,
                        robust_mode=True,
                        rebuild_mode=True,
                        title=title,
                        case_texts=case_texts,
                    ),
                    True,
                    'llm_rebuild',
                ))
            if robust_mode:
                prompt_order.append((
                    build_fix_prompt(
                        problem_text=problem_text,
                        code_text=code_text,
                        err_text=err_text,
                        trace_sum=trace_sum,
                        lesson_text=lesson_text,
                        fix_plan=guarded_plan,
                        scene=scene,
                        robust_mode=True,
                        rebuild_mode=False,
                        title=title,
                        case_texts=case_texts,
                    ),
                    True,
                    'llm_robust',
                ))
            prompt_order.append((
                build_fix_prompt(
                    problem_text=problem_text,
                    code_text=code_text,
                    err_text=err_text,
                    trace_sum=trace_sum,
                    lesson_text=lesson_text,
                    fix_plan=guarded_plan,
                    scene=scene,
                    robust_mode=False,
                    rebuild_mode=False,
                    title=title,
                    case_texts=case_texts,
                ),
                False,
                'llm',
            ))

            errors: list[str] = []
            for prompt, prompt_robust, source_name in prompt_order:
                try:
                    fixed = self._chat_fix(prompt=prompt, problem_text=problem_text, scene=scene, robust_mode=prompt_robust, title=title, case_texts=case_texts)
                    self.last_source = source_name
                    self.last_error = ''
                    return fixed
                except Exception as exc:  # noqa: BLE001
                    errors.append(f'{source_name}={exc}')

            self.last_source = 'fallback'
            self.last_error = ' | '.join(errors)
            if settings.llm_strict:
                raise RuntimeError(f'FixAgent 真实模型修复失败：{self.last_error}')

        note = [
            '# AUTO_FIX_NOTE:',
            f'# {fix_plan}',
        ]
        if code_text.startswith('# AUTO_FIX_NOTE:'):
            return code_text
        self.last_source = 'fallback'
        return '\n'.join(note) + '\n' + code_text
