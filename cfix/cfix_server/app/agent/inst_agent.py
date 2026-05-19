"""指令代理封装，负责承接对应阶段的大模型调用。"""

import ast
from dataclasses import dataclass


TRACE_PREFIX = "__CFIX_TRACE__"


_HELPER_SRC = f'''
import json as cfix_json

def cfix_short(value):
    try:
        text = repr(value)
    except Exception as exc:
        text = f"<repr_error:{{type(exc).__name__}}>"
    if len(text) > 180:
        text = text[:177] + "..."
    return text


def cfix_emit(event, **kwargs):
    payload = {{"event": event}}
    for key, value in kwargs.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            payload[key] = value
        else:
            payload[key] = cfix_short(value)
    print("{TRACE_PREFIX}" + cfix_json.dumps(payload, ensure_ascii=False))
'''


@dataclass
class _FnCtx:
    name: str


class _TraceInst(ast.NodeTransformer):
    """轻量 AST 插桩器。"""

    def __init__(self):
        self.fn_stack: list[_FnCtx] = []
        self.tmp_idx = 0

    def _cur_fn(self) -> str | None:
        return self.fn_stack[-1].name if self.fn_stack else None

    @staticmethod
    def _const(value):
        return ast.Constant(value=value)

    @staticmethod
    def _kw(key: str, value):
        return ast.keyword(arg=key, value=value)

    def _emit(self, event: str, **kwargs) -> ast.Expr:
        payload = {"func": self._const(self._cur_fn()), **kwargs}
        call = ast.Call(
            func=ast.Name(id="cfix_emit", ctx=ast.Load()),
            args=[self._const(event)],
            keywords=[self._kw(k, v) for k, v in payload.items()],
        )
        return ast.Expr(value=call)

    @staticmethod
    def _short_call(expr) -> ast.Call:
        return ast.Call(func=ast.Name(id="cfix_short", ctx=ast.Load()), args=[expr], keywords=[])

    def _capture_target_expr(self, node):
        """把 for/async for 的 target 转成可安全传给 cfix_short 的表达式。

        对于 `for i, p in ...` 这类解包目标，不能直接把 AST target 传进
        `_short_call`，否则 `ast.unparse` 会生成 `cfix_short(i, p)`，从而让
        trace helper 自己抛 TypeError，污染真正的运行轨迹。
        """
        if isinstance(node, ast.Name):
            return ast.Name(id=node.id, ctx=ast.Load())
        if isinstance(node, ast.Tuple):
            return ast.Tuple(elts=[self._capture_target_expr(elt) for elt in node.elts], ctx=ast.Load())
        if isinstance(node, ast.List):
            return ast.List(elts=[self._capture_target_expr(elt) for elt in node.elts], ctx=ast.Load())
        if hasattr(ast, "unparse"):
            return self._const(ast.unparse(node))
        return self._const('for_target')

    def _name_ids(self, node) -> list[str]:
        names: list[str] = []
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                names.extend(self._name_ids(elt))
        return names

    def _assign_logs(self, names: list[str], line_no: int | None) -> list[ast.stmt]:
        logs: list[ast.stmt] = []
        for name in names:
            logs.append(
                self._emit(
                    "var",
                    var=self._const(name),
                    line=self._const(line_no),
                    value=self._short_call(ast.Name(id=name, ctx=ast.Load())),
                )
            )
        return logs

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name.startswith('__') and node.name.endswith('__'):
            return node
        self.fn_stack.append(_FnCtx(node.name))
        node = self.generic_visit(node)
        arg_names = [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
        if node.args.vararg:
            arg_names.append("*" + node.args.vararg.arg)
        if node.args.kwarg:
            arg_names.append("**" + node.args.kwarg.arg)
        enter = self._emit(
            "enter",
            line=self._const(getattr(node, "lineno", None)),
            detail=self._const(", ".join(arg_names) if arg_names else "no-args"),
        )
        node.body = [enter] + node.body
        self.fn_stack.pop()
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if node.name.startswith('__') and node.name.endswith('__'):
            return node
        self.fn_stack.append(_FnCtx(node.name))
        node = self.generic_visit(node)
        enter = self._emit(
            "enter",
            line=self._const(getattr(node, "lineno", None)),
            detail=self._const("async"),
        )
        node.body = [enter] + node.body
        self.fn_stack.pop()
        return node

    def visit_Assign(self, node: ast.Assign):
        node = self.generic_visit(node)
        names: list[str] = []
        for target in node.targets:
            names.extend(self._name_ids(target))
        return [node, *self._assign_logs(names, getattr(node, "lineno", None))]

    def visit_AnnAssign(self, node: ast.AnnAssign):
        node = self.generic_visit(node)
        return [node, *self._assign_logs(self._name_ids(node.target), getattr(node, "lineno", None))]

    def visit_AugAssign(self, node: ast.AugAssign):
        node = self.generic_visit(node)
        return [node, *self._assign_logs(self._name_ids(node.target), getattr(node, "lineno", None))]

    def visit_If(self, node: ast.If):
        node = self.generic_visit(node)
        node.body = [
            self._emit("branch", line=self._const(getattr(node, "lineno", None)), branch=self._const("if_true"))
        ] + node.body
        if node.orelse:
            node.orelse = [
                self._emit("branch", line=self._const(getattr(node, "lineno", None)), branch=self._const("if_false"))
            ] + node.orelse
        return node

    def visit_For(self, node: ast.For):
        node = self.generic_visit(node)
        target_text = ast.unparse(node.target) if hasattr(ast, "unparse") else "for_target"
        capture_expr = self._capture_target_expr(node.target)
        node.body = [
            self._emit(
                "loop",
                line=self._const(getattr(node, "lineno", None)),
                var=self._const(target_text),
                value=self._short_call(capture_expr),
            )
        ] + node.body
        return node

    def visit_AsyncFor(self, node: ast.AsyncFor):
        node = self.generic_visit(node)
        target_text = ast.unparse(node.target) if hasattr(ast, "unparse") else "for_target"
        capture_expr = self._capture_target_expr(node.target)
        node.body = [
            self._emit(
                "loop",
                line=self._const(getattr(node, "lineno", None)),
                var=self._const(target_text),
                value=self._short_call(capture_expr),
            )
        ] + node.body
        return node

    def visit_While(self, node: ast.While):
        node = self.generic_visit(node)
        node.body = [
            self._emit("loop", line=self._const(getattr(node, "lineno", None)), var=self._const("while"), value=self._const("body"))
        ] + node.body
        return node

    def visit_Return(self, node: ast.Return):
        node = self.generic_visit(node)
        self.tmp_idx += 1
        tmp_name = f"cfix_ret_{self.tmp_idx}"
        if node.value is None:
            log = self._emit("ret", line=self._const(getattr(node, "lineno", None)), value=self._const("None"))
            return [log, node]
        assign_tmp = ast.Assign(targets=[ast.Name(id=tmp_name, ctx=ast.Store())], value=node.value)
        log = self._emit(
            "ret",
            line=self._const(getattr(node, "lineno", None)),
            value=self._short_call(ast.Name(id=tmp_name, ctx=ast.Load())),
        )
        ret = ast.Return(value=ast.Name(id=tmp_name, ctx=ast.Load()))
        return [assign_tmp, log, ret]


class InstAgent:
    """插桩代理：把代码改写成可观测版本，再交给 trace runner 执行。"""

    @staticmethod
    def _insert_helpers(tree: ast.Module) -> ast.Module:
        helper_nodes = ast.parse(_HELPER_SRC).body
        insert_at = 0

        # 先跳过模块 docstring，再跳过 __future__ import，避免破坏语义。
        if tree.body:
            first = tree.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str):
                insert_at = 1

        idx = insert_at
        while idx < len(tree.body):
            stmt = tree.body[idx]
            if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
                insert_at = idx + 1
                idx += 1
                continue
            break

        tree.body[insert_at:insert_at] = helper_nodes
        return tree

    @staticmethod
    def _fallback(code_text: str) -> str:
        lines = code_text.splitlines()
        out = []
        for line in lines:
            out.append(line)
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))
            if stripped.startswith("def ") and stripped.endswith(":"):
                pad = " " * (indent + 4)
                out.append(f'{pad}print("TRACE_ENTER: fallback")')
        return "\n".join(out)

    def run(
        self,
        code_text: str,
        err_text: str = "",
        inst_sugg: str = "",
        problem_text: str = "",
        scene: str = "func",
    ) -> str:
        try:
            tree = ast.parse(code_text)
            tree = _TraceInst().visit(tree)
            ast.fix_missing_locations(tree)
            tree = self._insert_helpers(tree)
            ast.fix_missing_locations(tree)
            return ast.unparse(tree)
        except Exception:
            return self._fallback(code_text)
