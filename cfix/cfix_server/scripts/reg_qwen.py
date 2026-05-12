#!/usr/bin/env python3
"""qwen 真链路 + Trace/Fix 回归脚本。

用途：
1. 不依赖数据库，直接验证“生成 -> 执行 -> trace -> 分析 -> 修复”研究核心；
2. 支持 strict 模式，避免模型失败时静默退回占位逻辑；
3. 生成 JSON + Markdown 双报告，便于论文第四章和答辩准备直接取材；
4. 统一“题目级通过率 / 用例级通过率 / 修复成功率”的统计口径，避免字段歧义。

示例：
python scripts/reg_qwen.py --dataset mbpp --samples 5 --max-round 3 --out-dir data/out/reg_qwen
python scripts/reg_qwen.py --dataset class_bank --samples 8 --max-round 3 --out-dir data/out/reg_qwen_class
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from app.agent.ana_agent import AnaAgent
from app.agent.fix_agent import FixAgent
from app.agent.gen_agent import GenAgent
from app.agent.inst_agent import InstAgent
from app.core.cfg import settings
from app.data.bench_bank import get_dataset_names, get_exp_problems
from app.sand.runner import Runner
from app.sand.trace_wrap import iter_trace_payloads, payload_to_text, summarize_trace


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run qwen trace/fix regression without DB.")
    parser.add_argument("--dataset", default="mbpp", choices=get_dataset_names(), help="题目来源")
    parser.add_argument("--samples", type=int, default=5, help="回归题目数量")
    parser.add_argument("--max-round", type=int, default=3, help="最大修复轮次")
    parser.add_argument("--out-dir", default="data/out/reg_qwen", help="报告输出目录")
    parser.add_argument("--require-real", action="store_true", help="要求必须启用真实模型，否则立即退出")
    return parser.parse_args()


def eval_cases(runner: Runner, code_text: str, cases: list[dict]) -> EvalPack:
    total_cnt = len(cases)
    pass_cnt = 0
    first_fail = None
    first_fail_case = None
    merged_stdout: list[str] = []
    merged_stderr: list[str] = []
    case_rows: list[dict] = []

    for case in cases:
        rs = runner.run_one(code_text, case["assert_text"])
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
                "time_ms": rs.time_ms,
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
    )


def make_lesson(round_no: int, err_text: str, fix_plan: str, pass_cnt: int, total_cnt: int, action: str) -> str:
    return (
        f"第{round_no}轮；错误：{(err_text or '未知错误')[:120]}；"
        f"策略：{(fix_plan or '无')[:120]}；通过：{pass_cnt}/{total_cnt}；动作：{action}"
    )


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_case_row_from_reg(item: dict, case_type: str, reason: str) -> dict:
    rounds = item.get("rounds") or []
    final_cases = item.get("final_cases") or []
    failed_cases = [x for x in final_cases if (x.get("result") or "") != "pass"]
    target_round = rounds[-1] if rounds else {}
    return {
        "case_type": case_type,
        "problem_no": item.get("problem_no"),
        "title": item.get("title"),
        "scene": item.get("scene"),
        "reason": reason,
        "round_used": int(item.get("round_used") or 0),
        "init_pass_cnt": int(item.get("init_pass_cnt") or 0),
        "final_pass_cnt": int(item.get("final_pass_cnt") or 0),
        "total_cnt": int(item.get("total_cnt") or 0),
        "gen_source": item.get("gen_source"),
        "trace_event_cnt": int(target_round.get("trace_event_cnt") or 0),
        "latest_action": target_round.get("action"),
        "root_cause": target_round.get("root_cause") or "-",
        "fix_plan": target_round.get("fix_plan") or "-",
        "latest_trace_sum": target_round.get("trace_sum") or "暂无轨迹摘要",
        "latest_trace_preview": target_round.get("trace_preview") or [],
        "first_failed_case": failed_cases[0] if failed_cases else None,
        "failed_case_cnt": len(failed_cases),
    }


def build_case_pack(report: dict) -> dict:
    items = report.get("items") or []
    success_candidates = [
        x for x in items if x.get("repaired") and x.get("final_result") == "pass" and x.get("init_result") != "pass"
    ]
    rollback_candidates = [
        x for x in items if any((rd.get("action") == "rollback") for rd in (x.get("rounds") or [])) and x.get("final_result") == "pass"
    ]
    failure_candidates = [x for x in items if x.get("final_result") != "pass"]

    def pick(rows, keyfn):
        return sorted(rows, key=keyfn, reverse=True)[0] if rows else None

    success = pick(
        success_candidates,
        lambda x: (
            int(x.get("round_used") or 0),
            int(x.get("final_pass_cnt") or 0) - int(x.get("init_pass_cnt") or 0),
            -int(x.get("problem_no") or 0),
        ),
    )
    rollback = pick(
        rollback_candidates,
        lambda x: (
            sum(1 for rd in (x.get("rounds") or []) if rd.get("action") == "rollback"),
            int(x.get("round_used") or 0),
            -int(x.get("problem_no") or 0),
        ),
    )
    failure = pick(
        failure_candidates,
        lambda x: (int(x.get("round_used") or 0), int(x.get("final_pass_cnt") or 0), -int(x.get("problem_no") or 0)),
    )

    return {
        "success_case": _build_case_row_from_reg(success, "success", "初始失败后被真实修复，适合展示完整成功闭环。") if success else None,
        "rollback_case": _build_case_row_from_reg(rollback, "rollback", "中途触发 rollback 且最终通过，适合展示收敛控制。") if rollback else None,
        "failure_case": _build_case_row_from_reg(failure, "failure", "最终仍未通过，适合分析当前方法的边界。") if failure else None,
    }


def build_summary(items: list[dict]) -> dict:
    sample_cnt = len(items)
    case_cnt_total = sum(int(item.get("total_cnt") or 0) for item in items)
    init_pass_problem_cnt = sum(1 for item in items if item.get("init_result") == "pass")
    final_pass_problem_cnt = sum(1 for item in items if item.get("final_result") == "pass")
    improved_problem_cnt = sum(1 for item in items if int(item.get("final_pass_cnt") or 0) > int(item.get("init_pass_cnt") or 0))
    repaired_problem_cnt = sum(
        1
        for item in items
        if item.get("init_result") != "pass" and item.get("final_result") == "pass"
    )
    trace_non_empty_problem_cnt = sum(1 for item in items if item.get("trace_non_empty"))
    rollback_problem_cnt = sum(1 for item in items if any((rd.get("action") == "rollback") for rd in (item.get("rounds") or [])))
    init_case_pass_cnt_total = sum(int(item.get("init_pass_cnt") or 0) for item in items)
    final_case_pass_cnt_total = sum(int(item.get("final_pass_cnt") or 0) for item in items)
    round_used_total = sum(int(item.get("round_used") or 0) for item in items)

    init_problem_pass_rate = (init_pass_problem_cnt / sample_cnt) if sample_cnt else 0.0
    final_problem_pass_rate = (final_pass_problem_cnt / sample_cnt) if sample_cnt else 0.0
    improved_problem_rate = (improved_problem_cnt / sample_cnt) if sample_cnt else 0.0
    repaired_problem_rate = (repaired_problem_cnt / sample_cnt) if sample_cnt else 0.0
    init_case_pass_rate = (init_case_pass_cnt_total / case_cnt_total) if case_cnt_total else 0.0
    final_case_pass_rate = (final_case_pass_cnt_total / case_cnt_total) if case_cnt_total else 0.0
    avg_round_used = (round_used_total / sample_cnt) if sample_cnt else 0.0

    return {
        "sample_cnt": sample_cnt,
        "case_cnt_total": case_cnt_total,
        "init_pass_problem_cnt": init_pass_problem_cnt,
        "final_pass_problem_cnt": final_pass_problem_cnt,
        "improved_problem_cnt": improved_problem_cnt,
        "repaired_problem_cnt": repaired_problem_cnt,
        "rollback_problem_cnt": rollback_problem_cnt,
        "trace_non_empty_problem_cnt": trace_non_empty_problem_cnt,
        "init_case_pass_cnt_total": init_case_pass_cnt_total,
        "final_case_pass_cnt_total": final_case_pass_cnt_total,
        "avg_round_used": round(avg_round_used, 2),
        "init_problem_pass_rate": round(init_problem_pass_rate, 4),
        "final_problem_pass_rate": round(final_problem_pass_rate, 4),
        "improved_problem_rate": round(improved_problem_rate, 4),
        "repaired_problem_rate": round(repaired_problem_rate, 4),
        "init_case_pass_rate": round(init_case_pass_rate, 4),
        "final_case_pass_rate": round(final_case_pass_rate, 4),
        # 兼容旧字段：明确规定它们现在表示“题目级通过率 / 修复成功率”。
        "init_pass_rate": round(init_problem_pass_rate, 4),
        "final_pass_rate": round(final_problem_pass_rate, 4),
        "repair_success_rate": round(repaired_problem_rate, 4),
    }


def build_md(report: dict) -> str:
    summary = report["summary"]
    lines = []
    lines.append("# qwen Trace/Fix 回归报告")
    lines.append("")
    lines.append(f"- 模型启用：{report['meta']['llm_ready']}")
    lines.append(f"- strict 模式：{report['meta']['llm_strict']}")
    lines.append(f"- provider / model：{report['meta']['provider']} / {report['meta']['model']}")
    lines.append(f"- 数据集：{report['meta']['dataset']}")
    lines.append(f"- 场景：{report['meta']['scene_mix']}")
    lines.append(f"- 样本数：{summary['sample_cnt']}")
    lines.append(f"- 用例总数：{summary['case_cnt_total']}")
    lines.append(f"- 初始题目级通过率：{summary['init_problem_pass_rate']:.2%}")
    lines.append(f"- 最终题目级通过率：{summary['final_problem_pass_rate']:.2%}")
    lines.append(f"- 初始用例级通过率：{summary['init_case_pass_rate']:.2%}")
    lines.append(f"- 最终用例级通过率：{summary['final_case_pass_rate']:.2%}")
    lines.append(f"- 修复成功率（初始失败且最终通过）：{summary['repaired_problem_rate']:.2%}")
    lines.append(f"- 改善题目占比（最终通过用例数高于初始）：{summary['improved_problem_rate']:.2%}")
    lines.append(f"- rollback 题目数：{summary['rollback_problem_cnt']}")
    lines.append(f"- trace 非空题目数：{summary['trace_non_empty_problem_cnt']}")
    lines.append(f"- 平均修复轮次：{summary['avg_round_used']:.2f}")
    lines.append("")
    lines.append("## 统计口径说明")
    lines.append("")
    lines.append("- 题目级通过率：统计通过全部测试用例的题目占比。")
    lines.append("- 用例级通过率：统计所有 assert 中通过的用例占比。")
    lines.append("- 修复成功率：仅统计“初始失败但最终通过”的题目占比。")
    lines.append("- 改善题目占比：统计最终通过用例数高于初始的题目占比，即使尚未全通过也计入改善。")
    lines.append("")
    lines.append("## 单题结果")
    lines.append("")
    lines.append("|题号|标题|场景|初始|最终|轮次|修复成功|trace非空|生成源|分析源|修复源|")
    lines.append("|---|---|---|---:|---:|---:|---|---|---|---|---|")
    for item in report['items']:
        ana_src = "/".join(sorted(set(x['ana_source'] for x in item['rounds']))) if item['rounds'] else "-"
        fix_src = "/".join(sorted(set(x['fix_source'] for x in item['rounds']))) if item['rounds'] else "-"
        lines.append(
            f"|{item['problem_no']}|{item['title']}|{item.get('scene', '-') }|{item['init_pass_cnt']}/{item['total_cnt']}|"
            f"{item['final_pass_cnt']}/{item['total_cnt']}|{item['round_used']}|"
            f"{'是' if item['repaired'] else '否'}|{'是' if item.get('trace_non_empty') else '否'}|{item['gen_source']}|{ana_src or '-'}|{fix_src or '-'}|"
        )

    lines.append("")
    lines.append("## 典型 round 摘要")
    lines.append("")
    for item in report['items']:
        lines.append(f"### #{item['problem_no']} {item['title']}")
        if not item['rounds']:
            lines.append("- 初始代码已通过，无需修复。")
            lines.append("")
            continue
        for rd in item['rounds']:
            lines.append(
                f"- Round {rd['round_no']}: before={rd['before_pass_cnt']}/{item['total_cnt']} -> "
                f"after={rd['after_pass_cnt']}/{item['total_cnt']} | action={rd['action']} | trace={rd['trace_event_cnt']}"
            )
            lines.append(f"  - 根因：{rd['root_cause']}")
            lines.append(f"  - 方案：{rd['fix_plan']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.require_real and not settings.llm_ready:
        raise SystemExit("当前 .env 未启用真实模型，无法执行 qwen 真链路回归。")

    problems = get_exp_problems(args.dataset, args.samples)
    runner = Runner()
    inst_agent = InstAgent()
    items: list[dict] = []

    for problem in problems:
        gen_agent = GenAgent()
        ana_agent = AnaAgent()
        fix_agent = FixAgent()

        current_code = gen_agent.run(problem['problem_text'], problem.get('scene', 'func'))
        best_code = current_code
        best_score = -1.0
        previous_score = None
        lessons: list[str] = []
        round_logs: list[dict] = []
        problem_trace_non_empty = False

        init_eval = eval_cases(runner, current_code, problem['cases'])
        current_eval = init_eval
        if current_eval.score > best_score:
            best_score = current_eval.score
            best_code = current_code

        for round_no in range(1, args.max_round + 1):
            if current_eval.result == 'pass':
                break

            fail = current_eval.first_fail
            fail_case = current_eval.first_fail_case or problem['cases'][0]
            err_text = (fail.tb_text or fail.err_msg or 'unknown error') if fail else 'unknown error'

            inst_code = inst_agent.run(
                code_text=current_code,
                err_text=err_text,
                inst_sugg=round_logs[-1]['inst_sugg'] if round_logs else '',
                problem_text=problem['problem_text'],
            )
            trace_rs = runner.run_trace_one(inst_code, fail_case['assert_text'])
            trace_items = list(iter_trace_payloads(trace_rs.stdout or ''))
            trace_sum = summarize_trace(
                trace_rs.stdout or '',
                err_type=trace_rs.err_type,
                err_msg=trace_rs.err_msg,
                line_no=trace_rs.line_no,
            )
            trace_event_cnt = len(trace_items)
            if trace_event_cnt:
                problem_trace_non_empty = True

            lesson_text = "\n".join(lessons[-3:])
            plan = ana_agent.run(
                problem_text=problem['problem_text'],
                code_text=current_code,
                err_text=err_text,
                trace_sum=trace_sum,
                lesson_text=lesson_text,
            )

            new_code = fix_agent.run(
                problem_text=problem['problem_text'],
                code_text=current_code,
                fix_plan=plan['fix_plan'],
                err_text=err_text,
                trace_sum=trace_sum,
                lesson_text=lesson_text,
            )
            new_eval = eval_cases(runner, new_code, problem['cases'])

            action = 'continue'
            if new_eval.score > best_score:
                action = 'accept'
                best_score = new_eval.score
                best_code = new_code
            elif previous_score is not None and new_eval.score < previous_score:
                action = 'rollback'
                new_code = best_code
                new_eval = eval_cases(runner, new_code, problem['cases'])
            else:
                action = 'continue'

            lessons.append(make_lesson(round_no, err_text, plan['fix_plan'], new_eval.pass_cnt, new_eval.total_cnt, action))
            round_logs.append(
                {
                    'round_no': round_no,
                    'before_pass_cnt': current_eval.pass_cnt,
                    'after_pass_cnt': new_eval.pass_cnt,
                    'before_score': current_eval.score,
                    'after_score': new_eval.score,
                    'trace_event_cnt': trace_event_cnt,
                    'trace_sum': trace_sum,
                    'trace_preview': [payload_to_text(x) for x in trace_items[:8]],
                    'root_cause': plan['root_cause'],
                    'fix_plan': plan['fix_plan'],
                    'inst_sugg': plan['inst_sugg'],
                    'ana_source': ana_agent.last_source,
                    'ana_error': ana_agent.last_error,
                    'fix_source': fix_agent.last_source,
                    'fix_error': fix_agent.last_error,
                    'action': action,
                    'first_fail_assert': fail_case['assert_text'],
                }
            )

            current_code = new_code
            current_eval = new_eval
            previous_score = new_eval.score

        item = {
            'problem_no': problem['problem_no'],
            'title': problem['title'],
            'scene': problem.get('scene', 'func'),
            'problem_text': problem['problem_text'],
            'total_cnt': init_eval.total_cnt,
            'init_pass_cnt': init_eval.pass_cnt,
            'final_pass_cnt': current_eval.pass_cnt,
            'init_result': init_eval.result,
            'final_result': current_eval.result,
            'round_used': len(round_logs),
            'repaired': init_eval.result != 'pass' and current_eval.result == 'pass',
            'improved': current_eval.pass_cnt > init_eval.pass_cnt,
            'trace_non_empty': problem_trace_non_empty,
            'gen_source': gen_agent.last_source,
            'gen_error': gen_agent.last_error,
            'rounds': round_logs,
            'final_cases': current_eval.case_rows,
        }
        items.append(item)

    summary = build_summary(items)
    report = {
        'meta': {
            'dataset': args.dataset,
            'samples': args.samples,
            'max_round': args.max_round,
            'llm_ready': settings.llm_ready,
            'llm_strict': settings.llm_strict,
            'provider': settings.llm_provider,
            'model': settings.llm_model,
            'sandbox_backend': settings.sandbox_backend,
            'scene_mix': '/'.join(sorted(set(item.get('scene', 'func') for item in items))),
        },
        'summary': summary,
        'items': items,
    }
    report['case_pack'] = build_case_pack(report)

    json_path = out_dir / 'reg_qwen.json'
    md_path = out_dir / 'reg_qwen.md'
    case_json_path = out_dir / 'reg_qwen_case_pack.json'
    case_md_path = out_dir / 'reg_qwen_case_pack.md'
    write_json(json_path, report)
    md_path.write_text(build_md(report), encoding='utf-8')
    write_json(case_json_path, report['case_pack'])

    case_md_lines = [
        '# qwen 典型案例包',
        '',
        f"- provider / model：{settings.llm_provider} / {settings.llm_model}",
        f"- dataset：{args.dataset}",
        f"- samples：{args.samples}",
        '',
    ]
    for key, label in [('success_case', '修复成功案例'), ('rollback_case', 'rollback 生效案例'), ('failure_case', '最终失败案例')]:
        item = report['case_pack'].get(key)
        case_md_lines.append(f'## {label}')
        case_md_lines.append('')
        if not item:
            case_md_lines.append('- 当前回归结果中暂无该类型案例。')
            case_md_lines.append('')
            continue
        case_md_lines.extend([
            f"- 题号：#{item.get('problem_no')}",
            f"- 标题：{item.get('title')}",
            f"- 场景：{item.get('scene')}",
            f"- 选择原因：{item.get('reason')}",
            f"- 轮次：{item.get('round_used')}",
            f"- 通过情况：{item.get('init_pass_cnt')}/{item.get('total_cnt')} -> {item.get('final_pass_cnt')}/{item.get('total_cnt')}",
            f"- 最新动作：{item.get('latest_action')}",
            f"- 根因：{item.get('root_cause')}",
            f"- 修复方案：{item.get('fix_plan')}",
            f"- 轨迹摘要：{item.get('latest_trace_sum')}",
            '',
        ])
    case_md_path.write_text('\n'.join(case_md_lines), encoding='utf-8')

    print(f'JSON report: {json_path}')
    print(f'Markdown report: {md_path}')
    print(f'Case pack JSON: {case_json_path}')
    print(f'Case pack Markdown: {case_md_path}')
    print(
        f"final_problem_pass_rate={summary['final_problem_pass_rate']:.2%}, "
        f"final_case_pass_rate={summary['final_case_pass_rate']:.2%}, "
        f"repaired_problem_cnt={summary['repaired_problem_cnt']}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
