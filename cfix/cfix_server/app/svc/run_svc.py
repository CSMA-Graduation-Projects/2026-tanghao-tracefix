from sqlalchemy.orm import Session

from app.models.run import RunRecord, CaseResult
from app.repo.task_repo import add_run, list_cases, add_case_result_batch
from app.sand.runner import Runner
from app.svc.trace_svc import TraceService
from app.core.scene_policy import get_scene_policy
from app.utils.case_block import normalize_case_rows, split_block_setup_assert
from app.utils.fail_focus import build_file_focus_summary


class RunService:
    def __init__(self):
        self.runner = Runner()
        self.trace_svc = TraceService()

    @staticmethod
    def _case_preview(text: str, limit: int = 120) -> str:
        src = (text or '').strip().replace('\n', ' | ')
        return src if len(src) <= limit else src[: limit - 3] + '...'

    @staticmethod
    def _is_instrumentation_noise(msg: str | None) -> bool:
        s = (msg or '')
        markers = ['cfix_emit', '_MatchResult__cfix_emit', 'cfix_short', '_MatchResult__cfix_short', '__cfix_emit', '__cfix_short']
        return any(m in s for m in markers)

    def _pick_primary_fail(self, failed_pack: list[tuple]) -> tuple | None:
        if not failed_pack:
            return None

        def score(item):
            case, rs, _merged_prelude, _block_assert = item
            msg = rs.err_msg or rs.tb_text or ''
            timeout = 1 if (rs.err_type or '') == 'TimeoutError' else 0
            noise = 1 if self._is_instrumentation_noise(msg) else 0
            assertion = 0 if 'AssertionError' in msg else 1
            return (
                timeout,
                noise,
                assertion,
                int(getattr(case, 'sort_no', 0) or 0),
                int(getattr(case, 'id', 0) or 0),
            )

        return sorted(failed_pack, key=score)[0]

    def _build_fail_summary(self, failed_pack: list[tuple], max_items: int = 6) -> str:
        if not failed_pack:
            return ''
        lines = []
        for idx, item in enumerate(failed_pack[:max_items], start=1):
            case, rs = item[0], item[1]
            kind = (rs.err_type or rs.result or 'fail').strip()
            detail = (rs.err_msg or rs.tb_text or '').strip().replace('\n', ' ')
            lines.append(
                f"[{idx}] case#{getattr(case, 'id', '?')} {kind}: {detail} | snippet: {self._case_preview(getattr(case, 'assert_text', '') or '')}"
            )
        if len(failed_pack) > max_items:
            lines.append(f"... 其余失败用例 {len(failed_pack) - max_items} 条省略")
        return '\n'.join(lines)

    def run_version(
        self,
        db: Session,
        task_id: int,
        ver_id: int,
        round_no: int,
        code_text: str,
        trace_on: bool = True,
        problem_text: str = "",
        inst_sugg: str = "",
        scene: str = "func",
    ):
        policy = get_scene_policy(scene)
        raw_cases = list_cases(db, task_id)
        norm_cases = normalize_case_rows(policy.scene, raw_cases)
        setup_cases = [x for x in norm_cases if str(getattr(x, 'src_type', '') or '').lower() == 'setup']
        exec_cases = [x for x in norm_cases if x not in setup_cases]
        if not exec_cases:
            exec_cases = norm_cases
            setup_cases = []

        # 显式 setup 块始终共享到所有后续测试块。
        shared_setup_parts = [
            (x.assert_text or '').strip()
            for x in setup_cases
            if (x.assert_text or '').strip()
        ]

        total_cnt = 0
        pass_cnt = 0
        first_fail = None
        first_fail_case = None
        failed_pack: list[tuple] = []  # (case, rs, merged_prelude, block_assert)
        merged_stdout: list[str] = []
        merged_stderr: list[str] = []
        case_items: list[CaseResult] = []
        total_time_ms = 0

        # 不同任务类型采用不同执行策略：
        # - func：逐 case 独立执行；
        # - class：支持 block case，但 case 局部 setup 不向后累积，避免对象状态污染后续测试；
        # - file：允许 block case 的局部 setup 在通过后累积到后续 case，支持模块级渐进式状态验证。
        for case in exec_cases:
            case_text = (case.assert_text or '').strip()
            block_setup, block_assert = split_block_setup_assert(case_text)

            if not block_assert:
                # 纯 setup 块不参与计分；file 场景允许在通过后累积到后续块。
                if block_setup.strip() and policy.accumulate_block_setup:
                    shared_setup_parts.append(block_setup.strip())
                continue

            total_cnt += 1
            effective_setup_parts = [part for part in [*shared_setup_parts, block_setup.strip()] if part]
            merged_prelude = '\n\n'.join(effective_setup_parts)
            merged_case = '\n\n'.join([part for part in [merged_prelude.strip(), block_assert.strip()] if part])
            rs = self.runner.run_one(code_text, merged_case)

            total_time_ms += rs.time_ms
            if rs.stdout:
                merged_stdout.append(rs.stdout)
            if rs.stderr:
                merged_stderr.append(rs.stderr)

            if rs.ok:
                pass_cnt += 1
                # 仅显式 setup 块允许跨 case 共享；custom_block 内部的局部前置代码
                # （例如对象创建、局部变量赋值）不应在 file 场景下被隐式累积到后续 case。
                # 否则会把本应独立的测试块串成状态污染链，进而把后续失败误判成业务逻辑错误。
            else:
                failed_pack.append((case, rs, merged_prelude, block_assert))

            case_items.append(
                CaseResult(
                    run_id=0,
                    case_id=case.id,
                    result=rs.result,
                    actual_out=(rs.stdout or None),
                    err_msg=rs.err_msg,
                    time_ms=rs.time_ms,
                )
            )

        primary_fail = self._pick_primary_fail(failed_pack)
        primary_fail_prelude = ''
        primary_fail_assert = ''
        if primary_fail:
            first_fail_case, first_fail, primary_fail_prelude, primary_fail_assert = primary_fail
        fail_summary = self._build_fail_summary(failed_pack)
        focus_summary = build_file_focus_summary(failed_pack) if policy.scene == 'file' else ''
        merged_fail_text = '\n\n'.join([x for x in [fail_summary, focus_summary] if x])

        result = 'pass' if (total_cnt == 0 or pass_cnt == total_cnt) else 'fail'
        score = (pass_cnt / total_cnt) if total_cnt else 0.0

        run = RunRecord(
            task_id=task_id,
            ver_id=ver_id,
            round_no=round_no,
            run_type='test',
            result=result,
            pass_cnt=pass_cnt,
            total_cnt=total_cnt,
            score=score,
            err_type=first_fail.err_type if first_fail else None,
            err_msg=merged_fail_text or (first_fail.err_msg if first_fail else None),
            tb_text=merged_fail_text or (first_fail.tb_text if first_fail else None),
            stdout='\n'.join(merged_stdout),
            stderr='\n'.join(merged_stderr),
            time_ms=total_time_ms,
            line_no=first_fail.line_no if first_fail else None,
        )
        run = add_run(db, run)

        for item in case_items:
            item.run_id = run.id
        if case_items:
            add_case_result_batch(db, case_items)

        trace_items = []
        trace_sum = ''
        if trace_on and exec_cases:
            trace_case = first_fail_case or exec_cases[0]
            trace_err_text = merged_fail_text or ((first_fail.tb_text or first_fail.err_msg or '') if first_fail else '')
            if primary_fail:
                trace_assert_text = primary_fail_assert or trace_case.assert_text
                trace_prelude_text = primary_fail_prelude
            else:
                block_setup, block_assert = split_block_setup_assert(trace_case.assert_text)
                trace_assert_text = block_assert or trace_case.assert_text
                trace_prelude_text = '\n\n'.join([part for part in [*shared_setup_parts, block_setup.strip()] if part])
            trace_pack = self.trace_svc.trace_case(
                db=db,
                run_id=run.id,
                code_text=code_text,
                assert_text=trace_assert_text,
                prelude_text=trace_prelude_text,
                problem_text=problem_text,
                err_text=trace_err_text,
                inst_sugg=inst_sugg,
                scene=policy.scene,
            )
            trace_items = trace_pack['trace_items']
            trace_sum = trace_pack['trace_sum']

            if trace_items:
                from app.repo.task_repo import add_trace_batch

                add_trace_batch(db, trace_items)

        run.trace_sum = trace_sum
        db.commit()
        db.refresh(run)
        return run
