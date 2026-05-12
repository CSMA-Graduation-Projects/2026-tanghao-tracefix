from __future__ import annotations

import ast
from collections import defaultdict
from typing import Iterable

from app.utils.public_api import extract_required_public_names


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ''


def _clip(text: str, limit: int = 180) -> str:
    s = str(text or '').strip().replace('\n', ' | ')
    if len(s) <= limit:
        return s
    return s[: limit - 3] + '...'


def _assign_target_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    names: list[str] = []
    targets: list[ast.AST] = []
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


class _CaseContractVisitor(ast.NodeVisitor):
    def __init__(self):
        self.var_types: dict[str, str] = {}
        self.func_calls: dict[str, list[str]] = defaultdict(list)
        self.ctor_calls: dict[str, list[str]] = defaultdict(list)
        self.method_calls: dict[str, list[str]] = defaultdict(list)
        self.constants: list[str] = []
        self.behavior_asserts: list[str] = []
        self.exception_contracts: list[str] = []

    @staticmethod
    def _push(bucket: dict[str, list[str]], key: str, value: str, limit: int = 3):
        if not key:
            return
        rows = bucket.setdefault(key, [])
        if value and value not in rows:
            rows.append(value)
            if len(rows) > limit:
                del rows[limit:]

    def _push_behavior(self, value: str, limit: int = 8):
        item = _clip(value, 180)
        if item and item not in self.behavior_asserts:
            self.behavior_asserts.append(item)
            if len(self.behavior_asserts) > limit:
                del self.behavior_asserts[limit:]

    def _push_exception(self, value: str, limit: int = 4):
        item = _clip(value, 180)
        if item and item not in self.exception_contracts:
            self.exception_contracts.append(item)
            if len(self.exception_contracts) > limit:
                del self.exception_contracts[limit:]

    def visit_Assign(self, node: ast.Assign):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            ctor_name = node.value.func.id
            if ctor_name and ctor_name[:1].isupper():
                for name in _assign_target_names(node):
                    self.var_types[name] = ctor_name
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            ctor_name = node.value.func.id
            if ctor_name and ctor_name[:1].isupper():
                for name in _assign_target_names(node):
                    self.var_types[name] = ctor_name
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        rendered = _safe_unparse(node)
        func = node.func
        if isinstance(func, ast.Name):
            name = func.id
            if name[:1].isupper():
                self._push(self.ctor_calls, name, rendered)
            else:
                self._push(self.func_calls, name, rendered)
        elif isinstance(func, ast.Attribute):
            attr = func.attr
            owner = func.value
            owner_name = owner.id if isinstance(owner, ast.Name) else ''
            owner_type = self.var_types.get(owner_name)
            key = f'{owner_type}.{attr}' if owner_type else attr
            self._push(self.method_calls, key, rendered)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load) and node.id.isupper() and len(node.id) > 1 and node.id not in self.constants:
            self.constants.append(node.id)

    def visit_Assert(self, node: ast.Assert):
        test = _safe_unparse(node.test)
        if test:
            self._push_behavior(f'assert {test}')
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        call_text = ''
        for body_node in node.body:
            for sub in ast.walk(body_node):
                if isinstance(sub, ast.Call):
                    call_text = _safe_unparse(sub)
                    break
            if call_text:
                break
        for handler in node.handlers:
            exc_name = ''
            if isinstance(handler.type, ast.Name):
                exc_name = handler.type.id
            elif isinstance(handler.type, ast.Attribute):
                exc_name = _safe_unparse(handler.type)
            if exc_name and call_text:
                self._push_exception(f'{call_text} raises {exc_name}')
        self.generic_visit(node)


def extract_case_api_contract(case_texts: list[str]) -> dict:
    visitor = _CaseContractVisitor()
    for raw in case_texts or []:
        text = str(raw or '').strip()
        if not text:
            continue
        try:
            tree = ast.parse(text)
        except Exception:
            continue
        visitor.visit(tree)
    return {
        'functions': {k: list(v) for k, v in visitor.func_calls.items()},
        'constructors': {k: list(v) for k, v in visitor.ctor_calls.items()},
        'methods': {k: list(v) for k, v in visitor.method_calls.items()},
        'constants': _dedupe_keep_order(visitor.constants),
        'behavior_asserts': _dedupe_keep_order(visitor.behavior_asserts),
        'exception_contracts': _dedupe_keep_order(visitor.exception_contracts),
    }


def build_case_contract_text(problem_text: str, case_texts: list[str] | None = None, *, scene: str = 'func', title: str = '', max_lines: int = 12) -> str:
    contract = extract_case_api_contract(list(case_texts or []))
    lines: list[str] = []

    required = extract_required_public_names(problem_text, scene=scene, title=title)
    if required:
        lines.append('题目与标题明确要求的公开对象名（必须原样定义）：' + '、'.join(required))

    ctors = []
    for name, examples in sorted(contract['constructors'].items()):
        show = examples[:1] if examples else [name]
        ctors.append(f'{name}（例如 {show[0]}）')
    if ctors:
        lines.append('测试块中已经直接实例化/调用的公开对象：' + '；'.join(ctors[:4]))

    funcs = []
    for name, examples in sorted(contract['functions'].items()):
        if name in {'assert', 'print'}:
            continue
        funcs.append(examples[0] if examples else name)
    if funcs:
        lines.append('测试块中已经直接调用的函数：' + '；'.join(funcs[:4]))

    methods = []
    for name, examples in sorted(contract['methods'].items()):
        methods.append(examples[0] if examples else name)
    if methods:
        lines.append('测试块中已经直接调用的方法：' + '；'.join(methods[:6]))

    consts = [x for x in contract['constants'] if x not in {'TRUE', 'FALSE', 'NONE'}]
    if consts:
        lines.append('测试块中已出现的公开常量/哨兵：' + '、'.join(consts[:6]))

    behavior_asserts = list(contract.get('behavior_asserts') or [])
    if behavior_asserts:
        lines.append('测试块中已经明确写出的关键行为断言：' + '；'.join(behavior_asserts[:6]))

    exc_contracts = list(contract.get('exception_contracts') or [])
    if exc_contracts:
        lines.append('测试块中已经明确写出的异常契约：' + '；'.join(exc_contracts[:4]))

    if not lines:
        return ''
    text = '测试块已经明确给出的可执行 API 契约（必须以这些调用和断言为准适配代码，禁止建议“修改测试调用方式”）：\n'
    body = '\n'.join(f'- {line}' for line in lines[:max_lines])
    return text + body + '\n\n'


def build_case_behavior_guard(case_texts: list[str] | None = None, *, max_items: int = 6) -> str:
    contract = extract_case_api_contract(list(case_texts or []))
    pieces: list[str] = []
    for item in list(contract.get('behavior_asserts') or [])[:max_items]:
        pieces.append(item)
    for item in list(contract.get('exception_contracts') or [])[: max(0, max_items - len(pieces))]:
        pieces.append(item)
    if not pieces:
        return ''
    return '测试块已明确写出这些行为契约：' + '；'.join(pieces)


def looks_like_api_contract_error(err_text: str) -> bool:
    low = str(err_text or '').lower()
    markers = (
        'takes ', 'missing 1 required positional argument', 'missing 2 required positional arguments',
        'got an unexpected keyword argument', 'has no attribute', 'is not defined', 'object is not callable',
    )
    return any(marker in low for marker in markers)


def build_case_contract_guard(err_text: str, case_texts: list[str] | None = None, *, scene: str = 'func') -> str:
    if (scene or 'func').strip().lower() not in {'class', 'file'}:
        return ''
    if not looks_like_api_contract_error(err_text):
        return ''
    contract = extract_case_api_contract(list(case_texts or []))
    if not any(contract.values()):
        return ''
    points = [
        '当前失败已出现 TypeError / AttributeError / NameError 一类公开 API 契约不匹配信号。',
        '这些调用来自可执行测试块，应把测试调用当作真实接口基准来适配代码；不要在分析或修复计划里建议“修改测试调用方式”。',
    ]
    method_examples: list[str] = []
    for bucket in ('constructors', 'functions', 'methods'):
        for _name, examples in contract[bucket].items():
            method_examples.extend(examples)
    if method_examples:
        points.append('优先对齐这些已执行的调用样例：' + '；'.join(_dedupe_keep_order(method_examples)[:6]))
    behavior_guard = build_case_behavior_guard(case_texts, max_items=4)
    if behavior_guard:
        points.append(behavior_guard)
    return '\n'.join(points)
