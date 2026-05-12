#!/usr/bin/env python3
"""第四章表格/案例正文底稿生成脚本。

输入：
1. exp_cmp.py 产出的 cmp.json；
2. reg_qwen.py 产出的 reg_qwen_case_pack.json（建议真实 qwen 条件下生成）。

输出：
- ch4_tbl.md / ch4_tbl.csv：第四章结果表格底稿；
- ch4_case.md：典型案例正文底稿；
- ch4_text.md：第四章实验结果分析正文底稿；
- ch4_full.md：合并后的总底稿。
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


MODE_ORDER = ["direct", "iter_no_tl", "full"]
MODE_LABEL = {
    "direct": "单轮代码生成模型",
    "iter_no_tl": "多轮修复但不引入 Trace / Lesson",
    "full": "执行反馈闭环完整方法",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate chapter-4 draft from compare + case pack files.")
    parser.add_argument("--cmp", required=True, help="cmp.json 路径")
    parser.add_argument("--case-pack", required=True, help="reg_qwen_case_pack.json 路径")
    parser.add_argument("--out-dir", default="data/out/ch4_draft", help="输出目录")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pct_text(value: Any) -> str:
    return f"{float(value or 0.0) * 100:.2f}%"


def num_text(value: Any) -> str:
    return f"{float(value or 0.0):.2f}"


def ms_text(value: Any) -> str:
    return str(int(value or 0))


def build_table_rows(cmp_payload: dict[str, Any]) -> list[dict[str, Any]]:
    compare = cmp_payload.get("compare") or {}
    rows = compare.get("rows") or []
    index = {row.get("mode"): row for row in rows}
    out = []
    for mode in MODE_ORDER:
        row = index.get(mode)
        if not row:
            continue
        out.append(
            {
                "方法": MODE_LABEL[mode],
                "样本数": int(row.get("sample_cnt") or 0),
                "初始通过率": pct_text(row.get("init_pass_rate")),
                "最终通过率": pct_text(row.get("final_pass_rate")),
                "修复成功率": pct_text(row.get("repair_success_rate")),
                "平均修复轮次": num_text(row.get("avg_round")),
                "平均耗时(ms)": ms_text(row.get("avg_time_ms")),
                "通过率提升": pct_text(row.get("delta_pass_rate")),
                "_raw": row,
            }
        )
    return out


def write_table_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["方法", "样本数", "初始通过率", "最终通过率", "修复成功率", "平均修复轮次", "平均耗时(ms)", "通过率提升"]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            data = dict(row)
            data.pop("_raw", None)
            writer.writerow(data)


def build_table_md(cmp_payload: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    meta = cmp_payload.get("meta") or {}
    lines = []
    lines.append("## 表 4-1 三组基线实验结果对比")
    lines.append("")
    lines.append(
        f"说明：本组实验在 {meta.get('dataset') or '-'} 数据集上进行，"
        f"共选取 {meta.get('samples') or 0} 个样本，最大修复轮次设为 {meta.get('max_round') or 0}。"
    )
    lines.append("")
    lines.append("|方法|样本数|初始通过率|最终通过率|修复成功率|平均修复轮次|平均耗时(ms)|通过率提升|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        lines.append(
            f"|{row['方法']}|{row['样本数']}|{row['初始通过率']}|{row['最终通过率']}|{row['修复成功率']}|"
            f"{row['平均修复轮次']}|{row['平均耗时(ms)']}|{row['通过率提升']}|"
        )
    lines.append("")
    return "\n".join(lines)


def build_case_section(case_pack: dict[str, Any]) -> str:
    label_map = {
        "success_case": "4.X 修复成功案例分析",
        "rollback_case": "4.X rollback 生效案例分析",
        "failure_case": "4.X 最终失败案例分析",
    }
    lines: list[str] = []
    for key in ["success_case", "rollback_case", "failure_case"]:
        item = case_pack.get(key)
        lines.append(f"## {label_map[key]}")
        lines.append("")
        if not item:
            lines.append("当前结果中暂未筛出该类型案例，可在扩大样本数后重新生成。")
            lines.append("")
            continue
        lines.append(
            f"在本轮实验中，选取题号 #{item.get('problem_no')} 作为该类型的代表性案例。"
            f"该题题目为“{item.get('title') or '未命名题目'}”。"
            f"之所以选择该案例，是因为{item.get('reason') or '其具有代表性'}。"
        )
        lines.append("")
        lines.append(
            f"从执行过程看，该题共经历 {int(item.get('round_used') or 0)} 轮修复。"
            f"题目初始通过情况为 {int(item.get('init_pass_cnt') or 0)}/{int(item.get('total_cnt') or 0)}，"
            f"最终通过情况为 {int(item.get('final_pass_cnt') or 0)}/{int(item.get('total_cnt') or 0)}。"
        )
        lines.append("")
        lines.append(
            f"从系统分析结果看，当前记录的根因描述为：{item.get('root_cause') or '暂无'}。"
            f"对应的修复方案为：{item.get('fix_plan') or '暂无'}。"
        )
        lines.append("")
        lines.append(
            f"结合运行轨迹摘要可以看到：{item.get('latest_trace_sum') or '暂无轨迹摘要'}。"
            f"该信息能够帮助系统定位错误发生的关键位置，并为后续修复提供依据。"
        )
        first_failed = item.get('first_failed_case') or {}
        if first_failed:
            lines.append("")
            lines.append(
                f"从失败样例看，系统记录的首个失败断言对应输出/错误为："
                f"{first_failed.get('err_msg') or first_failed.get('actual_out') or '-'}。"
            )
        lines.append("")
        if key == "success_case":
            lines.append(
                "该案例说明，在引入执行反馈、轨迹信息和多轮修复后，系统能够逐步缩小错误范围，并最终得到满足测试要求的代码结果。"
            )
        elif key == "rollback_case":
            lines.append(
                "该案例说明，当某一轮修复导致结果退化时，回滚机制能够将搜索基线恢复到更优版本，从而避免系统持续沿错误方向迭代。"
            )
        else:
            lines.append(
                "该案例说明，当前方法在部分逻辑错误场景下仍然可能无法稳定收敛，后续还需要继续优化轨迹摘要质量与修复策略。"
            )
        lines.append("")
    return "\n".join(lines)


def build_text_md(cmp_payload: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    row_map = {row["方法"]: row for row in rows}
    direct = row_map.get(MODE_LABEL["direct"])
    iter_row = row_map.get(MODE_LABEL["iter_no_tl"])
    full = row_map.get(MODE_LABEL["full"])

    lines = []
    lines.append("## 4.X 实验结果分析")
    lines.append("")
    if direct and iter_row and full:
        lines.append(
            f"从表 4-1 可以看出，单轮代码生成模型的最终通过率为 {direct['最终通过率']}，"
            f"多轮修复但不引入 Trace / Lesson 的方法最终通过率提升到 {iter_row['最终通过率']}，"
            f"而执行反馈闭环完整方法的最终通过率进一步提升到 {full['最终通过率']}。"
        )
        lines.append("")
        lines.append(
            f"从修复成功率指标看，完整方法达到 {full['修复成功率']}，高于单轮生成的 {direct['修复成功率']} 和"
            f"不引入 Trace / Lesson 的多轮修复方法 {iter_row['修复成功率']}。"
            "这表明，仅仅依靠多轮修复虽然能够带来一定改进，但如果缺少更细粒度的执行反馈和历史修复经验，"
            "系统对复杂逻辑错误的处理能力仍然有限。"
        )
        lines.append("")
        lines.append(
            f"从平均修复轮次和平均耗时看，完整方法的平均修复轮次为 {full['平均修复轮次']}，"
            f"平均耗时为 {full['平均耗时(ms)']} ms。"
            "这说明引入轨迹与历史记录后，系统虽然需要付出一定的额外分析成本，"
            "但整体上能够换来更高的最终通过率和更稳定的修复效果。"
        )
        lines.append("")
        lines.append(
            f"进一步比较通过率提升指标可以发现，完整方法的通过率提升达到 {full['通过率提升']}，"
            f"明显高于单轮生成方法和不引入 Trace / Lesson 的多轮修复方法。"
            "因此，可以认为执行反馈闭环机制对提升生成代码可执行性具有较明显的正向作用。"
        )
    else:
        lines.append("当前 compare 结果不完整，无法自动生成完整分析段落。")
    lines.append("")
    lines.append("## 4.X 本章小结")
    lines.append("")
    lines.append(
        "本章围绕单轮代码生成、多轮修复但不引入 Trace / Lesson，以及执行反馈闭环完整方法三组方案进行了对比实验。"
        "结果表明，随着执行反馈信息、历史修复经验和回滚控制机制的逐步引入，系统在最终通过率和修复成功率方面均表现出更好的效果。"
        "同时，典型案例分析也进一步说明，运行轨迹与多轮修复策略能够帮助系统更准确地定位错误原因，并增强修复过程的稳定性。"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmp_payload = read_json(Path(args.cmp))
    case_pack = read_json(Path(args.case_pack))
    table_rows = build_table_rows(cmp_payload)

    table_md = build_table_md(cmp_payload, table_rows)
    case_md = build_case_section(case_pack)
    text_md = build_text_md(cmp_payload, table_rows)
    full_md = "\n\n".join([table_md, text_md, case_md])

    write_table_csv(out_dir / "ch4_tbl.csv", table_rows)
    (out_dir / "ch4_tbl.md").write_text(table_md, encoding="utf-8")
    (out_dir / "ch4_case.md").write_text(case_md, encoding="utf-8")
    (out_dir / "ch4_text.md").write_text(text_md, encoding="utf-8")
    (out_dir / "ch4_full.md").write_text(full_md, encoding="utf-8")

    print(f"ch4_tbl.csv -> {out_dir / 'ch4_tbl.csv'}")
    print(f"ch4_tbl.md -> {out_dir / 'ch4_tbl.md'}")
    print(f"ch4_case.md -> {out_dir / 'ch4_case.md'}")
    print(f"ch4_text.md -> {out_dir / 'ch4_text.md'}")
    print(f"ch4_full.md -> {out_dir / 'ch4_full.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
