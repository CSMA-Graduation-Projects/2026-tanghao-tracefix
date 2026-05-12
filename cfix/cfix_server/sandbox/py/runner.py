import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path


RESULT_PREFIX = "__CFIX_RESULT__"


def extract_line_no(tb_text: str) -> int | None:
    line_no = None
    for line in tb_text.splitlines():
        if ", line " in line:
            try:
                line_no = int(line.split(", line ")[1].split(",")[0])
            except Exception:  # noqa: BLE001
                pass
    return line_no


def normalize_guest_path(path_str: str) -> Path:
    """兼容容器内收到的 Windows/Posix 两种路径风格。"""
    norm = (path_str or "").strip().replace("\\", "/")
    return Path(norm)


def build_merged_code(code_path: Path, asserts_path: Path) -> str:
    code_text = code_path.read_text(encoding="utf-8")
    asserts_text = asserts_path.read_text(encoding="utf-8") if asserts_path.exists() else ""
    wrapper = f"""
import ast
import importlib.util
import sys
import types

_CFIX_CODE = {code_text!r}
_CFIX_ASSERTS = {asserts_text!r}


def _infer_imported_module_names(text: str) -> set[str]:
    names = set()
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


def _should_alias(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is None
    except Exception:
        return True


def _run():
    module = types.ModuleType('__cfix_module__')
    module.__file__ = '<cfix_generated_module>'
    module.__package__ = ''
    md = module.__dict__
    md['__name__'] = '__cfix_module__'

    aliases = {{'__cfix_module__'}} | {{name for name in _infer_imported_module_names(_CFIX_ASSERTS) if _should_alias(name)}}
    prev = {{}}
    try:
        for name in aliases:
            prev[name] = sys.modules.get(name)
            sys.modules[name] = module
        exec(_CFIX_CODE, md, md)
        runtime_globals = dict(md)
        runtime_globals['__name__'] = '__main__'
        exec(_CFIX_ASSERTS, runtime_globals, runtime_globals)
    finally:
        for name, old in prev.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


_run()
"""
    return wrapper


def parse_err_type(tb_text: str) -> str | None:
    for line in reversed(tb_text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped:
            return stripped.split(":", 1)[0].strip()
        if stripped.endswith("Error") or stripped.endswith("Exception"):
            return stripped
    return None


def main() -> int:
    if len(sys.argv) < 3:
        print(f"{RESULT_PREFIX}" + json.dumps({"ok": False, "err_msg": "missing args"}, ensure_ascii=False))
        return 2

    code_path = normalize_guest_path(sys.argv[1])
    asserts_path = normalize_guest_path(sys.argv[2])
    timeout_sec = int(os.getenv("CFIX_TIMEOUT_SEC", "8"))

    merged = build_merged_code(code_path, asserts_path)

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8", dir="/tmp") as fp:
        fp.write(merged)
        exec_file = Path(fp.name)

    cmd = [sys.executable, "-I", "-B", str(exec_file)]
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            encoding="utf-8",
            errors="replace",
        )
        time_ms = int((time.time() - start) * 1000)
        ok = proc.returncode == 0
        tb_text = proc.stderr if not ok else ""
        err_type = parse_err_type(tb_text) if not ok else None
        err_msg = None
        if not ok and tb_text:
            lines = [x.strip() for x in tb_text.splitlines() if x.strip()]
            err_msg = lines[-1] if lines else None

        payload = {
            "ok": ok,
            "result": "pass" if ok else "fail",
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "tb_text": tb_text,
            "err_type": err_type,
            "err_msg": err_msg,
            "line_no": extract_line_no(tb_text),
            "time_ms": time_ms,
        }
        print(RESULT_PREFIX + json.dumps(payload, ensure_ascii=False))
        return 0
    except subprocess.TimeoutExpired:
        time_ms = int((time.time() - start) * 1000)
        payload = {
            "ok": False,
            "result": "fail",
            "stdout": "",
            "stderr": "",
            "tb_text": "",
            "err_type": "TimeoutError",
            "err_msg": f"container execution timeout (>{timeout_sec}s)",
            "line_no": None,
            "time_ms": time_ms,
        }
        print(RESULT_PREFIX + json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        payload = {
            "ok": False,
            "result": "fail",
            "stdout": "",
            "stderr": traceback.format_exc(),
            "tb_text": traceback.format_exc(),
            "err_type": type(exc).__name__,
            "err_msg": str(exc),
            "line_no": None,
            "time_ms": int((time.time() - start) * 1000),
        }
        print(RESULT_PREFIX + json.dumps(payload, ensure_ascii=False))
        return 0
    finally:
        try:
            exec_file.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
