"""代码差异工具模块，负责提供可复用的辅助逻辑。"""

import difflib


def make_diff(a: str, b: str) -> str:
    return "\n".join(
        difflib.unified_diff(a.splitlines(), b.splitlines(), fromfile="old", tofile="new", lineterm="")
    )
