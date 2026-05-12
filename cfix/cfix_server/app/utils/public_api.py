from __future__ import annotations

import ast
import re
from typing import Iterable


_NAME_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_BULLET_NAME_RE = re.compile(r'^\s*[-•]\s*(?:class\s+)?([A-Za-z_][A-Za-z0-9_]*)\b')
_CORE_NAME_RE = re.compile(r'核心(?:类|函数)名必须为\s*([A-Za-z_][A-Za-z0-9_]*)')

_STOPWORDS = {
    'python', 'module', 'class', 'function', 'functions', 'methods', 'method', 'list', 'dict',
    'tuple', 'none', 'true', 'false', 'get', 'set', 'delete', 'render', 'items', 'scopes',
    'exp', 'mbpp', 'class_eval', 'file_ultra', 'post', 'put', 'patch', 'head', 'options',
    # 常见指令/助记符，出现在题面里通常表示 DSL 操作，不应被当作必须定义的公开对象。
    'push', 'add', 'sub', 'mul', 'div', 'dup', 'pop', 'swap', 'noop',
}

_CORE_INLINE_RE = re.compile(r'核心(?:类|函数)\s*([A-Za-z_][A-Za-z0-9_]*)')
_UPPER_CONST_RE = re.compile(r'\b([A-Z][A-Z0-9_]{1,})\b')
_SENTENCE_SPLIT_RE = re.compile(r'[。；;\n]+')
_UPPER_OPCODE_LIST_RE = re.compile(r'(?:\b[A-Z][A-Z0-9_]{1,}\b(?:\s+[A-Za-z_][A-Za-z0-9_]*)?\s*[,，、/])+\s*\b[A-Z][A-Z0-9_]{1,}\b')


def _dedupe_keep_order(names: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        key = str(name or '').strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _extract_title_names(title: str) -> list[str]:
    raw = re.sub(r'\[[^\]]*\]', ' ', str(title or ''))
    names: list[str] = []
    for token in _NAME_RE.findall(raw):
        low = token.lower()
        if low in _STOPWORDS:
            continue
        if token.isupper() and len(token) <= 2:
            continue
        if any(ch.isupper() for ch in token) or '_' in token:
            names.append(token)
    return _dedupe_keep_order(names)



def _extract_upper_constant_names(text: str) -> list[str]:
    """提取题面里真正像“公开常量/哨兵”的全大写名字。

    这里要避免把 StackMachine 这类指令助记符（PUSH/ADD/SUB/...）
    误识别成必须定义的公开对象。
    经验规则：
    1. 先按句子切分；
    2. 若某句里出现 3 个及以上全大写 token，且整体像逗号/斜杠分隔的指令列表，则整句跳过；
    3. 其余零散出现的 STOP / SKIP 这类 token 仍保留。
    """
    names: list[str] = []
    for raw in _SENTENCE_SPLIT_RE.split(str(text or '')):
        sent = raw.strip()
        if not sent:
            continue
        tokens = [tok for tok in _UPPER_CONST_RE.findall(sent) if tok.lower() not in _STOPWORDS]
        if not tokens:
            continue
        # 过滤“支持 PUSH x, ADD, SUB, MUL...”这类指令/操作符列表。
        if len(tokens) >= 3 and (_UPPER_OPCODE_LIST_RE.search(sent) or any(ch in sent for ch in ',，、/')):
            continue
        names.extend(tokens)
    return _dedupe_keep_order(names)

def extract_required_public_names(problem_text: str, scene: str = 'func', title: str = '') -> list[str]:
    """从题目描述中提取必须存在的公开对象名。

    目标不是做完美 NLP，而是围绕当前项目常见题面格式稳定抽取：
    - “核心类名必须为 X / 核心函数名必须为 X”
    - “必须提供的公开对象”下的 bullet 名称
    - “公开函数 / 常量 / 类”小节中的 bullet 名称
    """
    text = str(problem_text or '')
    names: list[str] = []

    for match in _CORE_NAME_RE.finditer(text):
        names.append(match.group(1))
    for match in _CORE_INLINE_RE.finditer(text):
        names.append(match.group(1))

    names.extend(_extract_title_names(title))

    names.extend(_extract_upper_constant_names(text))

    in_public_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if '必须提供的公开对象' in line or line.startswith('公开函数') or line.startswith('公开对象') or line.startswith('常量') or line.startswith('类'):
            in_public_section = True
            continue
        if line.startswith('【') and '公开对象' not in line:
            in_public_section = False
        if not in_public_section and not line.startswith(('-', '•')):
            continue
        m = _BULLET_NAME_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        low = name.lower()
        if low in _STOPWORDS:
            continue
        if scene == 'func' and name in {'Subscription', 'EmitResult'}:
            continue
        names.append(name)

    if scene == 'func' and not names and 'solve' in text:
        names.append('solve')
    return _dedupe_keep_order(names)


class _PublicNameVisitor(ast.NodeVisitor):
    def __init__(self):
        self.names: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.names.add(node.name)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._collect_target(target)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.target is not None:
            self._collect_target(node.target)

    def _collect_target(self, target: ast.AST):
        if isinstance(target, ast.Name):
            self.names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                if isinstance(elt, ast.Name):
                    self.names.add(elt.id)


def module_public_names(code_text: str) -> set[str]:
    src = str(code_text or '').strip()
    if not src:
        return set()
    try:
        tree = ast.parse(src)
    except Exception:
        return set()
    visitor = _PublicNameVisitor()
    visitor.visit(tree)
    return visitor.names


def missing_required_public_names(problem_text: str, code_text: str, scene: str = 'func', title: str = '') -> list[str]:
    required = extract_required_public_names(problem_text, scene=scene, title=title)
    if not required:
        return []
    present = module_public_names(code_text)
    return [name for name in required if name not in present]
