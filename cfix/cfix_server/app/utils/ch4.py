"""第四章实验指标与图表口径工具。

用途：
1. 统一实验页、后端报告接口、独立对比脚本的指标名与展示顺序；
2. 生成可直接用于前端展示和论文整理的结构化图表数据；
3. 尽量避免各处手写重复口径，降低论文与系统展示不一致的风险。
"""

from __future__ import annotations

from typing import Any

# 固定论文第四章常用指标顺序。
CH4_ORDER = [
    "sample_cnt",
    "init_pass_rate",
    "final_pass_rate",
    "repair_success_rate",
    "avg_round",
    "avg_time_ms",
    "delta_pass_rate",
]

CH4_LABELS = {
    "sample_cnt": "样本数",
    "init_pass_rate": "初始通过率",
    "final_pass_rate": "最终通过率",
    "repair_success_rate": "修复贡献率",
    "avg_round": "平均修复轮次",
    "avg_time_ms": "平均耗时(ms)",
    "delta_pass_rate": "通过率提升",
}


def _pct_text(value: float | int | None) -> str:
    return f"{float(value or 0) * 100:.2f}%"


def _num1_text(value: float | int | None) -> str:
    return f"{float(value or 0):.2f}"


def _int_text(value: float | int | None) -> str:
    return str(int(round(float(value or 0))))


def fmt_metric(metric_key: str, value: Any) -> str:
    """把统一指标格式化成适合前端与 Markdown 直出的文本。"""
    if metric_key in {"init_pass_rate", "final_pass_rate", "repair_success_rate", "delta_pass_rate"}:
        return _pct_text(value)
    if metric_key == "avg_round":
        return _num1_text(value)
    if metric_key in {"sample_cnt", "avg_time_ms"}:
        return _int_text(value)
    return str(value)


def build_ch4_metrics(report: dict) -> dict:
    """基于实验摘要生成论文第四章统一指标包。"""
    init_rate = float(report.get("init_pass_rate") or 0.0)
    final_rate = float(report.get("final_pass_rate") or 0.0)
    delta_rate = max(0.0, final_rate - init_rate)
    values = {
        "sample_cnt": int(report.get("sample_cnt") or 0),
        "init_pass_rate": round(init_rate, 4),
        "final_pass_rate": round(final_rate, 4),
        "repair_success_rate": round(float(report.get("repair_success_rate") or 0.0), 4),
        "avg_round": round(float(report.get("avg_round") or 0.0), 2),
        "avg_time_ms": int(report.get("avg_time_ms") or 0),
        "delta_pass_rate": round(delta_rate, 4),
    }
    metrics = [
        {
            "key": key,
            "label": CH4_LABELS[key],
            "value": values[key],
            "text": fmt_metric(key, values[key]),
        }
        for key in CH4_ORDER
    ]
    return {
        "metric_order": list(CH4_ORDER),
        "metrics": metrics,
        "values": values,
        "notes": [
            "初始通过率表示仅做单轮生成时的通过情况，可作为单轮生成基线。",
            "最终通过率表示完整实验链路结束后的结果。",
            "修复贡献率表示在全部样本中，依靠自动修复从初始失败转为最终通过的样本比例。",
            "通过率提升 = 最终通过率 - 初始通过率。",
        ],
    }


def build_case_type_rows(case_type_dist: dict[str, Any] | None) -> list[dict]:
    dist = dict(case_type_dist or {})
    label_map = {
        "repair_success": "修复成功案例",
        "rollback_effective": "rollback 生效案例",
        "final_failure": "最终失败案例",
        "ordinary": "普通案例",
    }
    rows = []
    for key in ["repair_success", "rollback_effective", "final_failure", "ordinary"]:
        rows.append({
            "key": key,
            "label": label_map[key],
            "count": int(dist.get(key) or 0),
        })
    return rows


def build_single_chart(report: dict, error_dist: list[dict] | None = None, case_type_dist: dict | None = None) -> dict:
    """生成单个实验详情页使用的统一图表数据。"""
    ch4 = build_ch4_metrics(report)
    case_rows = build_case_type_rows(case_type_dist)
    return {
        "metric_cards": ch4["metrics"],
        "figures": [
            {
                "key": "fig_pass",
                "title": "初始/最终通过率对比",
                "kind": "bar",
                "items": [
                    {"label": "初始通过率", "value": ch4["values"]["init_pass_rate"], "text": fmt_metric("init_pass_rate", ch4["values"]["init_pass_rate"])},
                    {"label": "最终通过率", "value": ch4["values"]["final_pass_rate"], "text": fmt_metric("final_pass_rate", ch4["values"]["final_pass_rate"])},
                    {"label": "通过率提升", "value": ch4["values"]["delta_pass_rate"], "text": fmt_metric("delta_pass_rate", ch4["values"]["delta_pass_rate"])},
                ],
            },
            {
                "key": "fig_eff",
                "title": "修复效率指标",
                "kind": "bar",
                "items": [
                    {"label": "修复贡献率", "value": ch4["values"]["repair_success_rate"], "text": fmt_metric("repair_success_rate", ch4["values"]["repair_success_rate"])},
                    {"label": "平均修复轮次", "value": ch4["values"]["avg_round"], "text": fmt_metric("avg_round", ch4["values"]["avg_round"])},
                    {"label": "平均耗时(ms)", "value": ch4["values"]["avg_time_ms"], "text": fmt_metric("avg_time_ms", ch4["values"]["avg_time_ms"])},
                ],
            },
            {
                "key": "fig_case",
                "title": "典型案例类型分布",
                "kind": "bar",
                "items": [
                    {"label": row["label"], "value": row["count"], "text": str(row["count"])}
                    for row in case_rows
                ],
            },
            {
                "key": "fig_err",
                "title": "错误类型分布",
                "kind": "bar",
                "items": [
                    {"label": item.get("name") or "未知", "value": int(item.get("count") or 0), "text": str(int(item.get("count") or 0))}
                    for item in (error_dist or [])
                ],
            },
        ],
    }



def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _rank_values(items: list[dict], prefer: str) -> list[dict]:
    reverse = prefer == "high"
    return sorted(items, key=lambda x: _safe_float(x.get("value")), reverse=reverse)


def _best_label(items: list[dict]) -> str:
    if not items:
        return "-"
    best_value = _safe_float(items[0].get("value"))
    winners = [item.get("label") or "-" for item in items if abs(_safe_float(item.get("value")) - best_value) < 1e-9]
    if len(winners) == len(items):
        return "持平"
    return " / ".join(winners)


def _rank_text(items: list[dict]) -> str:
    if not items:
        return "-"
    groups: list[dict] = []
    for item in items:
        value = _safe_float(item.get("value"))
        if groups and abs(_safe_float(groups[-1].get("value")) - value) < 1e-9:
            groups[-1]["labels"].append(item.get("label") or "-")
        else:
            groups.append({"value": value, "labels": [item.get("label") or "-"]})
    return " > ".join(" = ".join(group["labels"]) for group in groups)


def build_compare_summary(mode_rows: list[dict]) -> dict:
    """生成适合论文截图使用的三组对比结论摘要。"""
    rows = []
    for row in mode_rows:
        init_rate = _safe_float(row.get("init_pass_rate"))
        final_rate = _safe_float(row.get("final_pass_rate"))
        repair_success_rate = _safe_float(row.get("repair_success_rate"))
        avg_round = _safe_float(row.get("avg_round"))
        avg_time_ms = _safe_float(row.get("avg_time_ms"))
        rows.append({
            "exp_id": row.get("exp_id"),
            "mode": row.get("mode"),
            "label": row.get("label") or row.get("mode") or "-",
            "sample_cnt": int(row.get("sample_cnt") or 0),
            "init_pass_rate": init_rate,
            "final_pass_rate": final_rate,
            "repair_success_rate": repair_success_rate,
            "avg_round": avg_round,
            "avg_time_ms": avg_time_ms,
            "delta_pass_rate": max(0.0, final_rate - init_rate),
        })

    if not rows:
        return {"cards": [], "notes": [], "verdict": {}}

    def metric_items(metric_key: str):
        return [
            {"exp_id": row["exp_id"], "mode": row["mode"], "label": row["label"], "value": row[metric_key]}
            for row in rows
        ]

    final_rank = _rank_values(metric_items("final_pass_rate"), "high")
    round_rank = _rank_values(metric_items("avg_round"), "low")
    delta_rank = _rank_values(metric_items("delta_pass_rate"), "high")
    repair_rank = _rank_values(metric_items("repair_success_rate"), "high")

    cards = [
        {
            "key": "best_final_pass",
            "title": "最终通过率最高",
            "winner_label": _best_label(final_rank),
            "value_text": fmt_metric("final_pass_rate", _safe_float(final_rank[0].get("value")) if final_rank else 0),
            "desc": f"排序：{_rank_text(final_rank)}",
            "type": "success",
        },
        {
            "key": "best_avg_round",
            "title": "平均轮次最低",
            "winner_label": _best_label(round_rank),
            "value_text": fmt_metric("avg_round", _safe_float(round_rank[0].get("value")) if round_rank else 0),
            "desc": f"排序：{_rank_text(round_rank)}",
            "type": "warning",
        },
        {
            "key": "best_delta_pass",
            "title": "通过率提升最大",
            "winner_label": _best_label(delta_rank),
            "value_text": fmt_metric("delta_pass_rate", _safe_float(delta_rank[0].get("value")) if delta_rank else 0),
            "desc": f"排序：{_rank_text(delta_rank)}",
            "type": "primary",
        },
    ]

    full_chain = next((row for row in rows if row.get("mode") == "full_chain"), None)
    verdict = {
        "title": "完整链路稳定性判断",
        "level": "info",
        "label": "当前未选择完整链路",
        "summary": "本次对比结果中未包含完整链路方案，暂时无法判断其稳定性表现。",
        "bullets": [],
    }
    if full_chain:
        others = [row for row in rows if row.get("mode") != "full_chain"]
        final_best_other = max((_safe_float(item.get("final_pass_rate")) for item in others), default=full_chain["final_pass_rate"])
        repair_best_other = max((_safe_float(item.get("repair_success_rate")) for item in others), default=full_chain["repair_success_rate"])
        round_best_other = min((_safe_float(item.get("avg_round")) for item in others), default=full_chain["avg_round"])
        better_final = full_chain["final_pass_rate"] >= final_best_other - 1e-9
        better_repair = full_chain["repair_success_rate"] >= repair_best_other - 1e-9
        round_penalty = full_chain["avg_round"] - round_best_other
        if better_final and better_repair and round_penalty <= 0.3:
            verdict.update({
                "level": "success",
                "label": "完整链路更稳",
                "summary": "从最终通过率、修复贡献率和平均轮次综合看，完整链路在这组实验里表现出更好的稳定性。",
            })
        elif better_final and better_repair:
            verdict.update({
                "level": "warning",
                "label": "完整链路更偏稳健，但轮次略高",
                "summary": "完整链路在最终通过率和修复贡献率上占优，但平均轮次略高，更像是以更多修复成本换取稳定结果。",
            })
        elif better_final:
            verdict.update({
                "level": "info",
                "label": "完整链路最终结果更好，但优势有限",
                "summary": "完整链路的最终通过率更高，不过在修复贡献率或平均轮次上并没有同时形成明显优势。",
            })
        else:
            verdict.update({
                "level": "danger",
                "label": "本次对比下未体现明显稳定优势",
                "summary": "在当前这组实验中，完整链路没有同时取得更高的最终通过率和更好的修复效率，稳定性优势还不明显。",
            })
        verdict["bullets"] = [
            f"完整链路最终通过率：{fmt_metric('final_pass_rate', full_chain['final_pass_rate'])}；其它方案最高：{fmt_metric('final_pass_rate', final_best_other)}。",
            f"完整链路修复贡献率：{fmt_metric('repair_success_rate', full_chain['repair_success_rate'])}；其它方案最高：{fmt_metric('repair_success_rate', repair_best_other)}。",
            f"完整链路平均轮次：{fmt_metric('avg_round', full_chain['avg_round'])}；其它方案最低：{fmt_metric('avg_round', round_best_other)}。",
        ]

    notes = [
        "结论摘要区只根据当前已运行实验的真实统计结果自动生成，不对未运行样本做推断。",
        "完整链路稳定性判断主要参考最终通过率、修复贡献率和平均轮次三项指标，用于论文展示时可直接截图说明。",
    ]

    return {
        "cards": cards,
        "verdict": verdict,
        "notes": notes,
    }

def build_compare_rows(mode_rows: list[dict]) -> dict:
    """生成三组对比基线的统一表格与图表结构。"""
    rows = []
    for row in mode_rows:
        values = {
            "sample_cnt": int(row.get("sample_cnt") or 0),
            "init_pass_rate": round(float(row.get("init_pass_rate") or 0.0), 4),
            "final_pass_rate": round(float(row.get("final_pass_rate") or 0.0), 4),
            "repair_success_rate": round(float(row.get("repair_success_rate") or 0.0), 4),
            "avg_round": round(float(row.get("avg_round") or 0.0), 2),
            "avg_time_ms": int(row.get("avg_time_ms") or 0),
            "delta_pass_rate": round(float(row.get("final_pass_rate") or 0.0) - float(row.get("init_pass_rate") or 0.0), 4),
        }
        rows.append({
            "exp_id": row.get("exp_id"),
            "mode": row.get("mode"),
            "label": row.get("label") or row.get("mode"),
            **values,
            "text": {key: fmt_metric(key, val) for key, val in values.items()},
        })

    metric_groups = []
    for key in ["final_pass_rate", "repair_success_rate", "avg_round", "avg_time_ms", "delta_pass_rate"]:
        metric_groups.append({
            "metric_key": key,
            "metric_label": CH4_LABELS[key],
            "items": [
                {"exp_id": row.get("exp_id"), "label": row["label"], "value": row[key], "text": row["text"][key]}
                for row in rows
            ],
        })

    return {
        "metric_order": list(CH4_ORDER),
        "rows": rows,
        "groups": metric_groups,
        "summary": build_compare_summary(mode_rows),
        "notes": [
            "单轮生成：仅做初始代码生成并直接测试。",
            "多轮修复（无 Trace/Lesson）：允许迭代修复，但不使用轨迹与历史经验。",
            "完整方法：启用 Trace 与 Lesson，并保留 rollback 控制。",
        ],
    }
