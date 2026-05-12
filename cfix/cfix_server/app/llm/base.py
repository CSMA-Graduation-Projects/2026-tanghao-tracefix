import ast
import json
import re
from abc import ABC, abstractmethod
from typing import Iterable


class LLMBase(ABC):
    """大模型客户端统一抽象。

    当前项目里 `gen / ana / fix` 三个代理都只需要“单轮文本输入 -> 单轮文本输出”，
    所以先保留一个最简单的接口，便于在不大改业务层的前提下切换不同模型提供方。
    这里额外补了三类能力：
    1. 清理 qwen 推理型模型常见的 `<think>...</think>` 输出；
    2. 从混杂输出里稳定提取 JSON / Python 代码，减少真实链路抖动；
    3. 对“代码主体正确但仍带有转义引号”的源码做二次修复，避免把非法 Python 直接落库。
    """

    @abstractmethod
    def chat(self, prompt: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError

    @staticmethod
    def compact_lines(lines: Iterable[str]) -> str:
        return "\n".join(x for x in lines if x is not None)

    @staticmethod
    def strip_code_fence(text: str) -> str:
        raw = (text or "").strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines:
                lines = lines[1:]
            while lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return raw

    @staticmethod
    def strip_think(text: str) -> str:
        raw = text or ""
        raw = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"<thinking>[\s\S]*?</thinking>", "", raw, flags=re.IGNORECASE)
        return raw.strip()

    @classmethod
    def normalize_text(cls, text: str) -> str:
        return cls.strip_code_fence(cls.strip_think(text or "")).strip()

    @staticmethod
    def _decode_common_escapes(text: str) -> str:
        raw = text or ""
        return (
            raw
            .replace("\\r\\n", "\n")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\'", "'")
            .replace("\\\\", "\\")
        )

    @classmethod
    def _cleanup_bundle_code_segment(cls, text: str) -> str:
        raw = (text or "").strip().rstrip(',')
        if not raw:
            return ""
        if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
            raw = raw[1:-1]
        elif raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
            raw = raw[1:-1]
        raw = cls._decode_common_escapes(raw)
        return raw.strip()

    @staticmethod
    def _is_valid_python_source(text: str) -> bool:
        src = (text or "").strip()
        if not src:
            return False
        try:
            ast.parse(src)
            return True
        except Exception:
            return False

    @classmethod
    def _repair_escaped_python_source(cls, text: str) -> str:
        """修正“主体像 Python，但仍带转义引号”的源码。"""
        src = (text or "").strip()
        if not src:
            return ""
        if cls._is_valid_python_source(src):
            return src

        candidates = [
            cls._decode_common_escapes(src),
            cls._cleanup_bundle_code_segment(src),
            cls._decode_common_escapes(cls._cleanup_bundle_code_segment(src)),
            src.replace(r'\"\"\"', '"""').replace(r"\'\'\'", "'''").replace(r'\"', '"').replace(r"\'", "'"),
        ]
        for cand in candidates:
            cand = (cand or "").strip()
            if cand and cls._is_valid_python_source(cand):
                return cand
        return src

    @classmethod
    def looks_like_bundle_contaminated_code(cls, text: str) -> bool:
        raw = cls.strip_think(text or "").strip()
        if not raw:
            return False
        if raw.startswith('{') and '"code"' in raw and '"cases"' in raw:
            return True
        if re.search(r'"\s*,\s*"cases"\s*:', raw, flags=re.IGNORECASE | re.DOTALL):
            return True
        if '\\n' in raw and '\n' not in raw and raw.lstrip().startswith(('def ', 'class ', 'import ', 'from ')):
            return True
        return False

    @classmethod
    def sanitize_generated_code(cls, text: str) -> str:
        raw = cls.strip_think(text or "").strip()
        if not raw:
            return ""

        # 1) 标准 Markdown 代码块。
        fence_matches = list(re.finditer(r"```(?:python|py)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE))
        if fence_matches:
            blocks = [m.group(1).strip() for m in fence_matches if m.group(1).strip()]
            if blocks:
                return max(blocks, key=len).strip()

        # 2) 先尝试从合法 JSON 中提取 code 字段。
        try:
            payload = cls.extract_json_obj(raw)
            code_field = payload.get('code') if isinstance(payload, dict) else None
            if isinstance(code_field, str) and code_field.strip():
                return cls._cleanup_bundle_code_segment(code_field)
        except Exception:
            pass

        # 3) 兼容“bundle JSON 半合法/半损坏”的情况：截取 code 到 cases 之前。
        bundle_match = re.search(r'(?s)(?:^|\{)\s*"code"\s*:\s*(.+?)\s*,\s*"cases"\s*:', raw)
        if bundle_match:
            cleaned = cls._cleanup_bundle_code_segment(bundle_match.group(1))
            if cleaned:
                return cleaned

        # 4) 兼容“代码已经被截到前面，但尾部仍残留 `", "cases": ...`”。
        tail_match = re.search(r'"\s*,\s*"cases"\s*:', raw, flags=re.IGNORECASE | re.DOTALL)
        if tail_match:
            cleaned = cls._cleanup_bundle_code_segment(raw[:tail_match.start()])
            if cleaned:
                return cleaned

        # 5) 纯代码字符串但仍保留了转义换行。
        if '\\n' in raw and '\n' not in raw and raw.lstrip().startswith(('def ', 'class ', 'import ', 'from ')):
            return cls._decode_common_escapes(raw).strip()

        return raw

    @classmethod
    def extract_python_code(cls, text: str) -> str:
        raw = cls.sanitize_generated_code(text or "")
        if not raw:
            return ""

        cleaned = raw
        code_starts = ["import ", "from ", "def ", "class ", "async def "]
        best_idx = None
        for marker in code_starts:
            idx = cleaned.find(marker)
            if idx >= 0 and (best_idx is None or idx < best_idx):
                best_idx = idx
        if best_idx is not None:
            cleaned = cleaned[best_idx:]

        cleaned = cleaned.strip()
        return cls._repair_escaped_python_source(cleaned)

    @classmethod
    def extract_json_obj(cls, text: str) -> dict:
        raw = cls.strip_think(text or "").strip()
        if not raw:
            raise ValueError("模型没有返回 JSON 内容")

        fence_matches = list(re.finditer(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE))
        candidates = [raw]
        candidates.extend([m.group(1).strip() for m in fence_matches if m.group(1).strip()])

        for candidate in candidates:
            try:
                value = json.loads(candidate)
                if isinstance(value, dict):
                    return value
            except Exception:
                pass

        start = raw.find("{")
        if start < 0:
            raise ValueError("未找到 JSON 对象起始位置")

        depth = 0
        in_str = False
        esc = False
        for idx in range(start, len(raw)):
            ch = raw[idx]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    snippet = raw[start:idx + 1]
                    value = json.loads(snippet)
                    if isinstance(value, dict):
                        return value
                    raise ValueError("JSON 解析成功，但结果不是对象")

        raise ValueError("未能从模型输出中提取完整 JSON 对象")
