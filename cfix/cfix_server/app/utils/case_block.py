from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import ast


@dataclass
class NormCase:
    id: int | None
    src_type: str
    assert_text: str
    sort_no: int
    weight: float = 1.0
    case_in: str | None = None
    expect_out: str | None = None
    row_ids: list[int] = field(default_factory=list)


def _text(x: Any, name: str, default: Any = None):
    if isinstance(x, dict):
        return x.get(name, default)
    return getattr(x, name, default)


def _is_assert_like_stmt(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assert):
        return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        fn = node.value.func
        if isinstance(fn, ast.Name):
            return fn.id == 'assert_raises'
        if isinstance(fn, ast.Attribute):
            return fn.attr == 'assert_raises'
    return False


def _stmt_source_segments(text: str) -> list[tuple[ast.stmt, str]]:
    src = str(text or '').replace('\r\n', '\n').strip('\n')
    if not src.strip():
        return []
    try:
        mod = ast.parse(src)
    except SyntaxError:
        return []
    out: list[tuple[ast.stmt, str]] = []
    for node in mod.body:
        seg = ast.get_source_segment(src, node)
        if seg is None:
            return []
        out.append((node, seg.strip('\n')))
    return out


def has_assert_line(text: str) -> bool:
    segs = _stmt_source_segments(text)
    if segs:
        return any(_is_assert_like_stmt(node) for node, _seg in segs)
    for raw in (text or '').splitlines():
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        parts = [p.strip() for p in raw.split(';')]
        for part in parts:
            if part.startswith('assert ') or part.startswith('assert_raises('):
                return True
    return False


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(' '))


def _starts_with_continuation(text: str) -> bool:
    for raw in (text or '').splitlines():
        if not raw.strip():
            continue
        stripped = raw.lstrip()
        indent = _line_indent(raw)
        if indent == 0:
            return False
        return stripped.startswith(('except ', 'elif ', 'else:', 'finally:')) or stripped in {')', ']', '}'}
    return False


def _looks_like_comment_only_block(text: str) -> bool:
    has_nonempty = False
    for raw in str(text or '').splitlines():
        s = raw.strip()
        if not s:
            continue
        has_nonempty = True
        if not s.startswith('#'):
            return False
    return has_nonempty


def _looks_like_heading_comment_line(line: str) -> bool:
    s = str(line or '').strip()
    if not s or s.startswith('#'):
        return False
    low = s.lower()
    code_prefixes = (
        'assert ', 'assert_raises(', 'def ', 'class ', 'from ', 'import ', 'return ', 'raise ',
        'for ', 'while ', 'if ', 'elif ', 'else:', 'try:', 'except ', 'finally:', 'with '
    )
    if low.startswith(code_prefixes):
        return False
    # 明显代码片段不要转注释。
    if any(tok in s for tok in ('==', '!=', '>=', '<=', ' = ', '(', ')', '[', ']', '{', '}', 'lambda ', '.append(', '.set(', '.get(')):
        return False
    heading_prefixes = (
        '说明', '注释', '备注', '共享准备', '共享 helper', '共享helper', '测试块', '测试用例', '用例',
        'case', 'helper', '-', '—', '•', '* '
    )
    if low.startswith(heading_prefixes) or s[:1].isdigit():
        return True
    if any('\u4e00' <= ch <= '\u9fff' for ch in s):
        return True
    return False


def normalize_comment_lines(text: str) -> str:
    lines: list[str] = []
    for raw in str(text or '').replace('\r\n', '\n').split('\n'):
        s = raw.strip()
        if not s:
            lines.append('')
            continue
        if _looks_like_heading_comment_line(s):
            lines.append(f'# {s.lstrip("#").strip()}')
        else:
            lines.append(raw.rstrip())
    return '\n'.join(lines).strip('\n')


def split_text_blocks(raw: str) -> list[str]:
    """按空行拆分 file/class 测试块。"""
    src = normalize_comment_lines(raw)
    if not src.strip():
        return []
    blocks = [x.strip('\n') for x in src.split('\n\n')]
    return [x for x in blocks if x.strip()]


def merge_continuation_blocks(blocks: list[str]) -> list[str]:
    """修复被错误拆开的代码块。"""
    if not blocks:
        return []
    merged: list[str] = []
    for block in blocks:
        if merged and _starts_with_continuation(block):
            merged[-1] = (merged[-1].rstrip() + '\n' + block.lstrip()).strip('\n')
        else:
            merged.append(block.strip('\n'))
    return merged


def merge_comment_only_blocks(blocks: list[str]) -> list[str]:
    """把纯注释块并到相邻真实代码块，避免被误判成共享准备。"""
    if not blocks:
        return []
    merged: list[str] = []
    pending_comments: list[str] = []
    for block in blocks:
        cur = normalize_comment_lines(block).strip('\n')
        if not cur.strip():
            continue
        if _looks_like_comment_only_block(cur):
            pending_comments.append(cur)
            continue
        if pending_comments:
            cur = '\n'.join(pending_comments + [cur]).strip('\n')
            pending_comments = []
        merged.append(cur)
    if pending_comments:
        if merged:
            merged[-1] = ('\n'.join([merged[-1]] + pending_comments)).strip('\n')
        else:
            merged.extend(pending_comments)
    return merged


def split_block_setup_assert(text: str) -> tuple[str, str]:
    """把一个测试块拆成前置准备部分和断言部分。"""
    segs = _stmt_source_segments(text)
    if segs:
        first_assert_idx = None
        for idx, (node, _seg) in enumerate(segs):
            if _is_assert_like_stmt(node):
                first_assert_idx = idx
                break
        if first_assert_idx is None:
            return ('\n'.join(seg for _n, seg in segs).strip(), '')
        pre = '\n'.join(seg for _n, seg in segs[:first_assert_idx]).strip('\n')
        body = '\n'.join(seg for _n, seg in segs[first_assert_idx:]).strip('\n')
        return pre, body

    lines = (text or '').splitlines()
    pre_parts: list[str] = []
    body_parts: list[str] = []
    body_started = False
    for raw in lines:
        parts = [p for p in raw.split(';')]
        for part in parts:
            stmt = part.strip()
            if not stmt or stmt.startswith('#'):
                continue
            is_assert = stmt.startswith('assert ') or stmt.startswith('assert_raises(')
            if is_assert:
                body_started = True
            if body_started:
                body_parts.append(stmt)
            else:
                pre_parts.append(stmt)
    return ('\n'.join(pre_parts).strip(), '\n'.join(body_parts).strip())


def _sort_rows_stable(rows: list[Any]) -> list[Any]:
    indexed_rows = list(enumerate(rows))

    def sort_key(item):
        original_idx, r = item
        val = _text(r, 'sort_no', None)
        if val is not None:
            try:
                return int(val), original_idx
            except (ValueError, TypeError):
                pass
        rid = _text(r, 'id', None)
        try:
            ridv = int(rid) if rid is not None else 10**9
        except Exception:
            ridv = 10**9
        return original_idx, ridv

    return [r for _, r in sorted(indexed_rows, key=sort_key)]


def _normalize_non_file_rows(rows: list[Any]) -> list[NormCase]:
    out: list[NormCase] = []
    for new_idx, row in enumerate(_sort_rows_stable(rows), start=1):
        text = normalize_comment_lines(str(_text(row, 'assert_text', '') or '')).strip()
        if not text or _looks_like_comment_only_block(text):
            continue
        out.append(
            NormCase(
                id=_text(row, 'id'),
                src_type=str(_text(row, 'src_type', 'custom') or 'custom'),
                assert_text=text,
                sort_no=int(_text(row, 'sort_no', new_idx) or new_idx),
                weight=float(_text(row, 'weight', 1.0) or 1.0),
                case_in=_text(row, 'case_in'),
                expect_out=_text(row, 'expect_out'),
                row_ids=[_text(row, 'id')] if _text(row, 'id') is not None else [],
            )
        )
    return out


def _raw_blocks_from_rows(rows: list[Any]) -> list[tuple[str, list[int]]]:
    blocks: list[tuple[str, list[int]]] = []
    for row in _sort_rows_stable(rows):
        text = normalize_comment_lines(str(_text(row, 'assert_text', '') or '')).replace('\r\n', '\n').strip('\n')
        if not text.strip():
            continue
        row_id = _text(row, 'id')
        parts = split_text_blocks(text)
        if not parts:
            continue
        for part in parts:
            blocks.append((part, [row_id] if row_id is not None else []))
    return blocks


def normalize_case_rows(scene: str, rows: list[Any]) -> list[NormCase]:
    scene = str(scene or '').strip().lower()
    if scene not in {'file', 'class'}:
        return _normalize_non_file_rows(rows)

    raw_blocks = _raw_blocks_from_rows(rows)
    if not raw_blocks:
        return []

    texts = [x[0] for x in raw_blocks]
    merged_texts = merge_comment_only_blocks(merge_continuation_blocks(texts))

    merged_blocks: list[tuple[str, list[int]]] = []
    src_idx = 0
    for mtext in merged_texts:
        row_ids: list[int] = []
        acc = ''
        while src_idx < len(raw_blocks):
            block_text, ids = raw_blocks[src_idx]
            row_ids.extend(ids)
            acc = (acc.rstrip() + '\n' + block_text.strip()).strip('\n') if acc else block_text.strip('\n')
            src_idx += 1
            if acc == mtext:
                break
            if len(acc) >= len(mtext):
                break
        merged_blocks.append((mtext, [x for x in row_ids if x is not None]))

    out: list[NormCase] = []
    for text, row_ids in merged_blocks:
        text = normalize_comment_lines(text).strip()
        if not text or _looks_like_comment_only_block(text):
            continue
        _pre, body = split_block_setup_assert(text)
        out.append(
            NormCase(
                id=row_ids[0] if row_ids else None,
                src_type='custom_block' if body else 'setup',
                assert_text=text,
                sort_no=len(out) + 1,
                weight=1.0,
                row_ids=row_ids,
            )
        )

    return out
