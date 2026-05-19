"""本地安全执行器模块，负责代码执行隔离、调度与轨迹包装。"""

import ast
import contextlib
import importlib.util
import io
import sys
import time
import traceback
import types
from dataclasses import dataclass


@dataclass
class ExecResult:
    ok: bool
    result: str
    stdout: str
    stderr: str
    tb_text: str
    err_type: str | None
    err_msg: str | None
    line_no: int | None
    time_ms: int


def _extract_line_no(tb_text: str) -> int | None:
    line_no = None
    for line in tb_text.splitlines():
        if ", line " in line:
            try:
                line_no = int(line.split(", line ")[1].split(",")[0])
            except Exception:
                pass
    return line_no


def _infer_imported_module_names(text: str) -> set[str]:
    names: set[str] = set()
    src = str(text or '').strip()
    if not src:
        return names
    try:
        tree = ast.parse(src)
    except Exception:
        return names

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = str(alias.name or '').split('.')[0].strip()
                if name:
                    names.add(name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            name = str(node.module or '').split('.')[0].strip()
            if name:
                names.add(name)
    return names


def _should_alias_as_generated_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is None
    except Exception:
        return True


def _exec_with_virtual_module(code_text: str, assert_text: str) -> ExecResult:
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    start = time.perf_counter()

    requested_aliases = {
        name
        for name in _infer_imported_module_names(assert_text)
        if _should_alias_as_generated_module(name)
    }
    alias_names = {'__cfix_module__', *requested_aliases}

    module = types.ModuleType('__cfix_module__')
    module.__file__ = '<cfix_generated_module>'
    module.__package__ = ''
    module_globals = module.__dict__
    module_globals['__name__'] = '__cfix_module__'

    prev_modules: dict[str, object | None] = {}
    try:
        for name in alias_names:
            prev_modules[name] = sys.modules.get(name)
            sys.modules[name] = module

        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            exec(code_text or '', module_globals, module_globals)
            runtime_globals = dict(module_globals)
            runtime_globals['__name__'] = '__main__'
            exec(assert_text or '', runtime_globals, runtime_globals)

        end = time.perf_counter()
        return ExecResult(
            ok=True,
            result='pass',
            stdout=out_buf.getvalue(),
            stderr=err_buf.getvalue(),
            tb_text='',
            err_type=None,
            err_msg=None,
            line_no=None,
            time_ms=max(0, int((end - start) * 1000)),
        )
    except Exception as e:
        end = time.perf_counter()
        tb_text = traceback.format_exc()
        return ExecResult(
            ok=False,
            result='fail',
            stdout=out_buf.getvalue(),
            stderr=err_buf.getvalue(),
            tb_text=tb_text,
            err_type=e.__class__.__name__,
            err_msg=str(e),
            line_no=_extract_line_no(tb_text),
            time_ms=max(0, int((end - start) * 1000)),
        )
    finally:
        for name, old in prev_modules.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


def exec_python(code_text: str, asserts: list[str] | None = None) -> ExecResult:
    asserts = asserts or []
    merged_asserts = '\n'.join(asserts)
    return _exec_with_virtual_module(code_text or '', merged_asserts)


def exec_python_case(code_text: str, assert_text: str) -> ExecResult:
    return _exec_with_virtual_module(code_text or '', assert_text or '')
