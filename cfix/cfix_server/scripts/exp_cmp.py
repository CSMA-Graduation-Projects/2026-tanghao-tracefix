#!/usr/bin/env python3
"""三组基线实跑脚本。

用途：
1. 在不依赖数据库的情况下，直接对比三组方法：direct / iter_no_tl / full；
2. 支持真实 qwen 条件下运行，适合作为论文第四章的统一结果来源；
3. 统一输出 JSON / CSV / Markdown / chart JSON，方便前端与论文复用。

示例：
python scripts/exp_cmp.py --dataset mbpp --samples 10 --max-round 3 --out-dir data/out/exp_cmp --require-real
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agent.ana_agent import AnaAgent
from app.agent.fix_agent import FixAgent
from app.agent.gen_agent import GenAgent
from app.agent.inst_agent import InstAgent
from app.core.cfg import settings
from app.data.bench_bank import get_dataset_names, get_exp_problems
from app.sand.runner import Runner
from app.sand.trace_wrap import iter_trace_payloads, payload_to_text, summarize_trace
from app.utils.ch4 import build_compare_rows


MODE_META = {
    "direct": {"label": "单轮生成", "trace_on": False, "lesson_on": False, "iterative": False},
    "iter_no_tl": {"label": "多轮修复（无 Trace/Lesson）", "trace_on": False, "lesson_on": False, "iterative": True},
    "full": {"label": "完整方法", "trace_on": True, "lesson_on": True, "iterative": True},
}


@dataclass
class EvalPack:
    pass_cnt: int
    total_cnt: int
    score: float
    result: str
    first_fail: object | None
    first_fail_case: dict | None
    merged_stdout: str
    merged_stderr: str
    case_rows: list[dict]
    time_ms: int


@dataclass
class ModeResult:
    mode: str
    label: str
    sample_cnt: int
    init_pass_rate: float
    final_pass_rate: float
    repair_success_rate: float
    avg_round: float
    avg_time_ms: int
    items: list[dict]

    def to_row(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "label": self.label,
            "sample_cnt": self.sample_cnt,
            "init_pass_rate": round(float(self.init_pass_rate or 0.0), 4),
            "final_pass_rate": round(float(self.final_pass_rate or 0.0), 4),
            "repair_success_rate": round(float(self.repair_success_rate or 0.0), 4),
            "avg_round": round(float(self.avg_round or 0.0), 2),
            "avg_time_ms": int(self.avg_time_ms or 0),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run direct / iter_no_tl / full comparison without DB.")
    parser.add_argument("--dataset", default="mbpp", choices=get_dataset_names(), help="题目来源")
    parser.add_argument("--samples", type=int, default=10, help="题目数量")
    parser.add_argument("--max-round", type=int, default=3, help="最大修复轮次")
    parser.add_argument("--out-dir", default="data/out/exp_cmp", help="输出目录")
    parser.add_argument("--require-real", action="store_true", help="要求必须启用真实模型，否则立即退出")
    parser.add_argument("--modes", nargs="*", default=["direct", "iter_no_tl", "full"], help="可选子集：direct iter_no_tl full")
    return parser.parse_args()


def eval_cases(runner: Runner, code_text: str, cases: list[dict]) -> EvalPack:
    total_cnt = len(cases)
    pass_cnt = 0
    first_fail = None
    first_fail_case = None
    merged_stdout: list[str] = []
    merged_stderr: list[str] = []
    case_rows: list[dict] = []
    total_time_ms = 0

    for case in cases:
        rs = runner.run_one(code_text, case["assert_text"])
        total_time_ms += int(rs.time_ms or 0)
        if rs.ok:
            pass_cnt += 1
        elif first_fail is None:
            first_fail = rs
            first_fail_case = case

        if rs.stdout:
            merged_stdout.append(rs.stdout)
        if rs.stderr:
            merged_stderr.append(rs.stderr)

        case_rows.append(
            {
                "assert_text": case["assert_text"],
                "result": rs.result,
                "actual_out": rs.stdout or "",
                "err_type": rs.err_type,
                "err_msg": rs.err_msg,
                "time_ms": int(rs.time_ms or 0),
            }
        )

    score = (pass_cnt / total_cnt) if total_cnt else 0.0
    return EvalPack(
        pass_cnt=pass_cnt,
        total_cnt=total_cnt,
        score=score,
        result="pass" if pass_cnt == total_cnt else "fail",
        first_fail=first_fail,
        first_fail_case=first_fail_case,
        merged_stdout="\n".join(merged_stdout),
        merged_stderr="\n".join(merged_stderr),
        case_rows=case_rows,
        time_ms=total_time_ms,
    )


def make_lesson(round_no: int, err_text: str, fix_plan: str, pass_cnt: int, total_cnt: int, action: str) -> str:
    return (
        f"第{round_no}轮；错误：{(err_text or '未知错误')[:120]}；"
        f"策略：{(fix_plan or '无')[:120]}；通过：{pass_cnt}/{total_cnt}；动作：{action}"
    )


def _run_one_problem(problem: dict, runner: Runner, inst_agent: InstAgent, mode: str, max_round: int) -> dict:
    meta = MODE_META[mode]
    gen_agent = GenAgent()
    ana_agent = AnaAgent()
    fix_agent = FixAgent()

    current_code = gen_agent.run(problem["problem_text"], problem.get("scene", "func"))
    best_code = current_code
    lessons: list[str] = []
    round_logs: list[dict] = []

    init_eval = eval_cases(runner, current_code, problem["cases"])
    total_time_ms = int(init_eval.time_ms or 0)
    best_score = init_eval.score
    current_eval = init_eval
    previous_score = current_eval.score

    if meta["iterative"]:
        for round_no in range(1, max_round + 1):
            if current_eval.result == "pass":
                break

            fail = current_eval.first_fail
            fail_case = current_eval.first_fail_case or problem["cases"][0]
            err_text = (fail.tb_text or fail.err_msg or "unknown error") if fail else "unknown error"

            trace_sum = ""
            trace_preview: list[str] = []
            trace_event_cnt = 0
            if meta["trace_on"]:
                inst_code = inst_agent.run(
                    code_text=current_code,
                    err_text=err_text,
                    inst_sugg=round_logs[-1]["inst_sugg"] if round_logs else "",
                    problem_text=problem["problem_text"],
                )
                trace_rs = runner.run_trace_one(inst_code, fail_case["assert_text"])
                trace_items = list(iter_trace_payloads(trace_rs.stdout or ""))
                trace_preview = [payload_to_text(x) for x in trace_items[:8]]
                trace_sum = summarize_trace(
                    trace_rs.stdout or "",
                    err_type=trace_rs.err_type,
                    err_msg=trace_rs.err_msg,
                    line_no=trace_rs.line_no,
                )
                trace_event_cnt = len(trace_items)

            lesson_text = "\n".join(lessons[-3:]) if meta["lesson_on"] else ""
            plan = ana_agent.run(
                problem_text=problem["problem_text"],
                code_text=current_code,
                err_text=err_text,
                trace_sum=trace_sum,
                lesson_text=lesson_text,
            )

            new_code = fix_agent.run(
                problem_text=problem["problem_text"],
                code_text=current_code,
                fix_plan=plan["fix_plan"],
                err_text=err_text,
                trace_sum=trace_sum,
                lesson_text=lesson_text,
            )
            new_eval = eval_cases(runner, new_code, problem["cases"])
            total_time_ms += int(new_eval.time_ms or 0)

            action = "continue"
            if new_eval.score > best_score:
                action = "accept"
                best_score = new_eval.score
                best_code = new_code
            elif previous_score is not None and new_eval.score < previous_score:
                action = "rollback"
                new_code = best_code
                new_eval = eval_cases(runner, new_code, problem["cases"])
                total_time_ms += int(new_eval.time_ms or 0)
            else:
                action = "continue"

            if meta["lesson_on"]:
                lessons.append(make_lesson(round_no, err_text, plan["fix_plan"], new_eval.pass_cnt, new_eval.total_cnt, action))

            round_logs.append(
                {
                    "round_no": round_no,
                    "before_pass_cnt": current_eval.pass_cnt,
                    "after_pass_cnt": new_eval.pass_cnt,
                    "before_score": current_eval.score,
                    "after_score": new_eval.score,
                    "trace_event_cnt": trace_event_cnt,
                    "trace_sum": trace_sum,
                    "trace_preview": trace_preview,
                    "root_cause": plan["root_cause"],
                    "fix_plan": plan["fix_plan"],
                    "inst_sugg": plan["inst_sugg"],
                    "ana_source": ana_agent.last_source,
                    "ana_error": ana_agent.last_error,
                    "fix_source": fix_agent.last_source,
                    "fix_error": fix_agent.last_error,
                    "action": action,
                    "first_fail_assert": fail_case["assert_text"],
                }
            )

            current_code = new_code
            current_eval = new_eval
            previous_score = new_eval.score

    final_eval = current_eval
    rollback_cnt = sum(1 for x in round_logs if x["action"] == "rollback")
    return {
        "problem_no": int(problem["problem_no"]),
        "title": problem["title"],
        "scene": problem.get("scene", "func"),
        "problem_text": problem["problem_text"],
        "total_cnt": init_eval.total_cnt,
        "init_pass_cnt": init_eval.pass_cnt,
        "final_pass_cnt": final_eval.pass_cnt,
        "init_result": init_eval.result,
        "final_result": final_eval.result,
        "round_used": len(round_logs),
        "repaired": final_eval.pass_cnt > init_eval.pass_cnt,
        "gen_source": gen_agent.last_source,
        "gen_error": gen_agent.last_error,
        "rounds": round_logs,
        "final_cases": final_eval.case_rows,
        "time_ms": total_time_ms,
        "rollback_cnt": rollback_cnt,
        "trace_non_empty": any(int(x.get("trace_event_cnt") or 0) > 0 for x in round_logs),
    }


def _aggregate(mode: str, items: list[dict]) -> ModeResult:
    total = len(items)
    init_pass_cnt = sum(1 for x in items if x["init_result"] == "pass")
    final_pass_cnt = sum(1 for x in items if x["final_result"] == "pass")
    repair_cnt = sum(1 for x in items if x["repaired"])
    avg_round = (sum(float(x["round_used"] or 0) for x in items) / total) if total else 0.0
    avg_time_ms = int((sum(int(x.get("time_ms") or 0) for x in items) / total) if total else 0)
    return ModeResult(
        mode=mode,
        label=MODE_META[mode]["label"],
        sample_cnt=total,
        init_pass_rate=(init_pass_cnt / total) if total else 0.0,
        final_pass_rate=(final_pass_cnt / total) if total else 0.0,
        repair_success_rate=(repair_cnt / total) if total else 0.0,
        avg_round=avg_round,
        avg_time_ms=avg_time_ms,
        items=items,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "mode",
        "label",
        "sample_cnt",
        "init_pass_rate",
        "final_pass_rate",
        "repair_success_rate",
        "avg_round",
        "avg_time_ms",
        "delta_pass_rate",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            data = {key: row.get(key) for key in fieldnames}
            writer.writerow(data)


def _build_md(meta: dict, compare_rows: list[dict]) -> str:
    lines = []
    lines.append("# 三组基线实跑结果")
    lines.append("")
    lines.append(f"- provider / model：{meta['provider']} / {meta['model']}")
    lines.append(f"- dataset：{meta['dataset']}")
    lines.append(f"- samples：{meta['samples']}")
    lines.append(f"- max_round：{meta['max_round']}")
    lines.append(f"- llm_ready：{meta['llm_ready']}")
    lines.append(f"- llm_strict：{meta['llm_strict']}")
    lines.append("")
    lines.append("## 对比总表")
    lines.append("")
    lines.append("|方法|样本数|初始通过率|最终通过率|修复成功率|平均轮次|平均耗时(ms)|通过率提升|")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in compare_rows:
        lines.append(
            f"|{row['label']}|{row['sample_cnt']}|{row['text']['init_pass_rate']}|{row['text']['final_pass_rate']}|"
            f"{row['text']['repair_success_rate']}|{row['text']['avg_round']}|{row['text']['avg_time_ms']}|{row['text']['delta_pass_rate']}|"
        )

    lines.append("")
    lines.append("## 分方法摘要")
    lines.append("")
    for row in compare_rows:
        lines.append(f"### {row['label']}")
        lines.append("")
        lines.append(
            f"- 初始通过率：{row['text']['init_pass_rate']}；最终通过率：{row['text']['final_pass_rate']}；"
            f"修复成功率：{row['text']['repair_success_rate']}；平均轮次：{row['text']['avg_round']}；"
            f"平均耗时：{row['text']['avg_time_ms']}。"
        )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    modes = [x for x in args.modes if x in MODE_META]
    if not modes:
        raise SystemExit("未提供有效模式，可选：direct iter_no_tl full")

    if args.require_real and not settings.llm_ready:
        raise SystemExit("当前 .env 未启用真实模型，无法执行 qwen 基线实跑。")

    problems = get_exp_problems(args.dataset, args.samples)
    runner = Runner()
    inst_agent = InstAgent()

    detail_rows: list[dict] = []
    item_map: dict[str, list[dict]] = {}
    for mode in modes:
        items = [_run_one_problem(problem, runner, inst_agent, mode, args.max_round) for problem in problems]
        result = _aggregate(mode, items)
        item_map[mode] = items
        detail_rows.append(result.to_row())

    compare_pack = build_compare_rows(detail_rows)
    compare_rows = compare_pack["rows"]

    meta = {
        "dataset": args.dataset,
        "samples": args.samples,
        "max_round": args.max_round,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "llm_ready": settings.llm_ready,
        "llm_strict": settings.llm_strict,
        "sandbox_backend": settings.sandbox_backend,
        "modes": modes,
    }
    payload = {
        "meta": meta,
        "compare": compare_pack,
        "items": item_map,
    }

    _write_json(out_dir / "cmp.json", payload)
    _write_json(out_dir / "cmp_chart.json", {"meta": meta, "compare": compare_pack})
    _write_csv(out_dir / "cmp_sum.csv", compare_rows)
    (out_dir / "cmp.md").write_text(_build_md(meta, compare_rows), encoding="utf-8")

    print(f"cmp.json -> {out_dir / 'cmp.json'}")
    print(f"cmp_sum.csv -> {out_dir / 'cmp_sum.csv'}")
    print(f"cmp.md -> {out_dir / 'cmp.md'}")
    print(f"cmp_chart.json -> {out_dir / 'cmp_chart.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
