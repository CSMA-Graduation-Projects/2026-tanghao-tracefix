import json

TRACE_PREFIX = "__CFIX_TRACE__"


def _is_noise_error(err_msg: str | None) -> bool:
    s = (err_msg or "")
    markers = ["__cfix_emit", "_MatchResult__cfix_emit", "__cfix_short", "_MatchResult__cfix_short"]
    return any(m in s for m in markers)


def iter_trace_payloads(stdout: str):
    """从 stdout 中解析结构化 trace 行。"""
    for raw in (stdout or "").splitlines():
        if raw.startswith(TRACE_PREFIX):
            payload_text = raw[len(TRACE_PREFIX):].strip()
            try:
                yield json.loads(payload_text)
            except Exception:
                yield {"event": "raw", "text": payload_text}
        elif "TRACE" in raw or "DEBUG" in raw:
            yield {"event": "raw", "text": raw}


def payload_to_text(payload: dict) -> str:
    event = payload.get("event", "raw")
    if event == "enter":
        return f"进入函数 {payload.get('func') or '?'} @L{payload.get('line')}"
    if event == "var":
        return f"变量 {payload.get('var')}={payload.get('value')} @L{payload.get('line')}"
    if event == "branch":
        return f"分支 {payload.get('branch')} @L{payload.get('line')}"
    if event == "loop":
        return f"循环 {payload.get('var')}={payload.get('value')} @L{payload.get('line')}"
    if event == "ret":
        return f"返回 {payload.get('value')} @L{payload.get('line')}"
    if event == "error":
        return f"异常 {payload.get('err_type')}: {payload.get('err_msg')} @L{payload.get('line')}"
    return payload.get("text") or str(payload)


def summarize_trace(stdout: str, err_type: str | None = None, err_msg: str | None = None, line_no: int | None = None) -> str:
    """生成供分析代理直接消费的简短轨迹摘要。"""
    lines = [payload_to_text(p) for p in iter_trace_payloads(stdout)]
    if err_type:
        if _is_noise_error(err_msg):
            lines.append(f"插桩噪声: {err_type}: {err_msg or ''} @L{line_no}")
        else:
            lines.append(f"异常收敛点: {err_type}: {err_msg or ''} @L{line_no}")
    return "\n".join(lines[:50])
