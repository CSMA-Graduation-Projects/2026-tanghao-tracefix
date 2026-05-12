def build_fb(err_type: str | None, err_msg: str | None, line_no: int | None, pass_cnt: int, total_cnt: int, trace_sum: str | None, time_ms: int):
    return {
        "err_type": err_type,
        "err_msg": err_msg,
        "line_no": line_no,
        "pass_cnt": pass_cnt,
        "total_cnt": total_cnt,
        "trace_sum": trace_sum,
        "time_ms": time_ms,
    }
