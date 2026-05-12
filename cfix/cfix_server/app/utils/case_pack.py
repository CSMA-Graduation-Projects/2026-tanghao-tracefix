"""典型案例固化工具。

用途：
1. 从实验明细中挑选适合论文第四章展示的代表性案例；
2. 输出统一结构，便于后端 report / 前端导出 / 回归脚本复用；
3. 尽量使用稳定、可解释的排序规则，而不是随机挑样本。
"""

from __future__ import annotations

from typing import Any


def _norm_text(value: Any, default: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else default


def _build_case_payload(row: dict, case_type: str, reason: str) -> dict:
    failed_cases = row.get("latest_failed_cases") or []
    first_failed = failed_cases[0] if failed_cases else None
    trace_preview = row.get("latest_trace_preview") or []
    return {
        "case_type": case_type,
        "problem_no": row.get("problem_no"),
        "task_id": row.get("task_id"),
        "title": _norm_text(row.get("title"), "未命名题目"),
        "reason": reason,
        "round_used": int(row.get("round_used") or 0),
        "time_ms": int(row.get("time_ms") or 0),
        "err_type": _norm_text(row.get("err_type"), "-"),
        "rollback_cnt": int(row.get("rollback_cnt") or 0),
        "best_score": float(row.get("best_score") or 0),
        "typical_tags": list(row.get("typical_tags") or []),
        "latest_run_id": row.get("latest_run_id"),
        "latest_failed_run_id": row.get("latest_failed_run_id"),
        "latest_result": row.get("latest_result"),
        "latest_trace_sum": _norm_text(row.get("latest_trace_sum"), "暂无轨迹摘要"),
        "latest_trace_preview": trace_preview[:8],
        "first_failed_case": {
            "case_id": first_failed.get("case_id"),
            "result": first_failed.get("result"),
            "actual_out": _norm_text(first_failed.get("actual_out"), "-"),
            "err_msg": _norm_text(first_failed.get("err_msg"), "-"),
        } if first_failed else None,
        "failed_case_cnt": len(failed_cases),
        "best_ver_id": row.get("best_ver_id"),
        "latest_ver_id": row.get("latest_ver_id"),
        "init_ver_id": row.get("init_ver_id"),
    }


def _pick_best(rows: list[dict], *, score_fn) -> dict | None:
    if not rows:
        return None
    return sorted(rows, key=score_fn, reverse=True)[0]


def build_typical_cases(items: list[dict]) -> dict:
    """生成实验级典型案例包。

    返回结构：
    {
      success_case: {...} | None,
      rollback_case: {...} | None,
      failure_case: {...} | None,
      case_type_dist: {...},
      available_case_cnt: int,
    }
    """

    success_candidates = [
        row for row in items
        if bool(row.get("repair_ok")) and bool(row.get("final_pass")) and not bool(row.get("init_pass"))
    ]
    rollback_candidates = [
        row for row in items
        if bool(row.get("final_pass")) and int(row.get("rollback_cnt") or 0) > 0
    ]
    failure_candidates = [
        row for row in items
        if not bool(row.get("final_pass"))
    ]

    success_row = _pick_best(
        success_candidates,
        score_fn=lambda row: (
            int(row.get("round_used") or 0),
            int(row.get("failed_case_cnt") or len(row.get("latest_failed_cases") or [])),
            -int(row.get("time_ms") or 0),
            -int(row.get("problem_no") or 0),
        ),
    )
    rollback_row = _pick_best(
        rollback_candidates,
        score_fn=lambda row: (
            int(row.get("rollback_cnt") or 0),
            int(row.get("round_used") or 0),
            bool(row.get("repair_ok")),
            -int(row.get("problem_no") or 0),
        ),
    )
    failure_row = _pick_best(
        failure_candidates,
        score_fn=lambda row: (
            int(row.get("round_used") or 0),
            int(row.get("rollback_cnt") or 0),
            int(row.get("failed_case_cnt") or len(row.get("latest_failed_cases") or [])),
            -int(row.get("problem_no") or 0),
        ),
    )

    case_type_dist = {
        "repair_success": len(success_candidates),
        "rollback_effective": len(rollback_candidates),
        "final_failure": len(failure_candidates),
        "ordinary": max(
            0,
            len(items) - len({
                *(id(x) for x in success_candidates),
                *(id(x) for x in rollback_candidates),
                *(id(x) for x in failure_candidates),
            })
        ),
    }

    return {
        "success_case": _build_case_payload(success_row, "success", "从初始失败到最终通过，适合展示完整修复闭环。") if success_row else None,
        "rollback_case": _build_case_payload(rollback_row, "rollback", "出现真实 rollback 且最终通过，适合说明回滚机制如何稳定收敛。") if rollback_row else None,
        "failure_case": _build_case_payload(failure_row, "failure", "最终仍未通过，适合分析当前方法的边界与失败模式。") if failure_row else None,
        "case_type_dist": case_type_dist,
        "available_case_cnt": sum(1 for x in [success_row, rollback_row, failure_row] if x),
    }
