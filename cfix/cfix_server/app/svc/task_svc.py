"""任务编排服务，负责封装对应业务域的核心流程。"""

import traceback
from hashlib import sha256
from sqlalchemy.orm import Session

from app.models.task import Task
from app.llm.base import LLMBase
from app.models.case import TestCase
from app.models.ver import CodeVersion
from app.repo.task_repo import (
    create_task,
    add_case,
    get_task,
    get_latest_version,
    list_versions,
    list_cases,
    replace_cases,
    save_task,
)
from app.svc.gen_svc import GenService
from app.svc.run_svc import RunService
from app.svc.plan_svc import PlanService
from app.svc.fix_svc import FixService
from app.svc.lesson_svc import LessonService
from app.svc.rb_svc import RollbackDecision, RollbackService
from app.svc.model_svc import resolve_default_model_id
from app.utils.case_block import normalize_case_rows, has_assert_line


class TaskService:
    """负责把任务创建、执行、修复、lesson 与回退决策串成完整主流程。"""

    def __init__(self):
        # 各子服务在这里集中组装，便于任务链路统一编排。
        self.gen_svc = GenService()
        self.run_svc = RunService()
        self.plan_svc = PlanService()
        self.fix_svc = FixService()
        self.lesson_svc = LessonService()
        self.rb_svc = RollbackService()

    def _stop_requested(self, db: Session, task: Task) -> bool:
        db.refresh(task)
        return str(task.status or '').lower() == 'stop'


    @staticmethod
    def _has_assert(text: str) -> bool:
        return has_assert_line(text)

    @classmethod
    def _norm_case_src_type(cls, scene: str, src_type: str | None, assert_text: str) -> str:
        src = str(src_type or '').strip()
        if src:
            return src
        # class/file 场景下，含 assert 的块作为测试块；
        # 不含 assert 的块作为共享准备块，供后续测试复用。
        if scene in {'file', 'class'}:
            return 'custom_block' if cls._has_assert(assert_text) else 'setup'
        
        # 函数级任务默认按普通自定义用例处理。
        return 'custom'

    @staticmethod
    def _detect_case_mode(scene: str, cases: list[TestCase]) -> str:
        if scene not in {'file', 'class'}:
            return 'line'
        srcs = {str(getattr(x, 'src_type', '') or '').strip().lower() for x in (cases or [])}
        if any(src == 'setup' or 'block' in src for src in srcs):
            return 'block'
        return 'legacy_line'

    @classmethod
    def _legacy_case_warning(cls, task: Task, cases: list[TestCase]) -> str:
        mode = cls._detect_case_mode(str(task.scene or ''), cases)
        if mode != 'legacy_line':
            return ''
        return (
            '当前任务仍在使用旧版逐行测试用例（legacy_line）。'
            'file/class 场景下这会把多行测试块拆坏，导致反馈被语法/上下文噪声污染，'
            '自动修复会持续修测试块而不是修业务逻辑。请复制题目与测试块后重新创建一个新任务再运行。'
        )

    @classmethod
    def _assert_runnable_case_mode(cls, task: Task, cases: list[TestCase]):
        warning = cls._legacy_case_warning(task, cases)
        if warning:
            raise ValueError(warning)

    @staticmethod
    def _normalize_version_code(db: Session, ver: CodeVersion) -> str:
        raw = str(getattr(ver, 'code_text', '') or '')
        sanitized = LLMBase.sanitize_generated_code(raw)
        if sanitized and sanitized != raw:
            ver.code_text = sanitized
            ver.code_hash = sha256(sanitized.encode("utf-8")).hexdigest()
            db.add(ver)
            db.commit()
            db.refresh(ver)
            return sanitized
        return raw

    def create_new_task(self, db: Session, user_id: int, payload):
        # 若前端未显式选择模型，则兜底落到当前用户的默认模型配置。
        model_id = payload.model_id if getattr(payload, 'model_id', None) is not None else resolve_default_model_id(db, user_id)
        task = Task(
            user_id=user_id,
            sess_id=payload.sess_id,
            model_id=model_id,
            title=payload.title,
            lang=payload.lang,
            scene=payload.scene,
            dataset=payload.dataset,
            problem_text=payload.problem_text,
            max_round=payload.max_round,
            is_trace_on=payload.is_trace_on,
            is_lesson_on=payload.is_lesson_on,
        )
        task = create_task(db, task)

        # 构建原始测试用例列表，并对每个用例的源类型进行规范化处理
        raw_cases = [
            TestCase(
                task_id=task.id,
                src_type=self._norm_case_src_type(task.scene, item.src_type, item.assert_text),
                case_in=item.case_in,
                expect_out=item.expect_out,
                assert_text=item.assert_text,
                weight=item.weight,
                sort_no=item.sort_no,
            )
            for item in payload.cases
        ]
        # 进入数据库前先统一整理 block/setup 结构，避免后续运行阶段再补救脏数据。
        norm_cases = normalize_case_rows(task.scene, raw_cases)
        # 将标准化后的测试用例逐一添加到数据库中
        for item in norm_cases:
            add_case(
                db,
                TestCase(
                    task_id=task.id,
                    src_type=item.src_type,
                    case_in=item.case_in,
                    expect_out=item.expect_out,
                    assert_text=item.assert_text,
                    weight=item.weight,
                    sort_no=item.sort_no,
                ),
            )
        return task


    def replace_task_cases(self, db: Session, task_id: int, cases_payload: list):
        task = get_task(db, task_id)
        if not task:
            raise ValueError("任务不存在")

        raw_cases = [
            TestCase(
                task_id=task.id,
                src_type=self._norm_case_src_type(task.scene, getattr(item, 'src_type', None), getattr(item, 'assert_text', '')),
                case_in=getattr(item, 'case_in', None),
                expect_out=getattr(item, 'expect_out', None),
                assert_text=getattr(item, 'assert_text', ''),
                weight=float(getattr(item, 'weight', 1.0) or 1.0),
                sort_no=int(getattr(item, 'sort_no', idx) or idx),
            )
            for idx, item in enumerate(cases_payload or [], start=1)
        ]
        norm_cases = normalize_case_rows(task.scene, raw_cases)
        db_rows = [
            TestCase(
                task_id=task.id,
                src_type=item.src_type,
                case_in=item.case_in,
                expect_out=item.expect_out,
                assert_text=item.assert_text,
                weight=item.weight,
                sort_no=item.sort_no,
            )
            for item in norm_cases
        ]
        replace_cases(db, task.id, db_rows)
        return db_rows

    def update_task_meta(self, db: Session, task_id: int, payload):
        task = get_task(db, task_id)
        if not task:
            raise ValueError("任务不存在")

        if getattr(payload, 'sess_id', None) is not None:
            task.sess_id = int(payload.sess_id)
        if getattr(payload, 'title', None) is not None:
            title = str(payload.title or '').strip()
            if not title:
                raise ValueError('任务标题不能为空')
            task.title = title
        if getattr(payload, 'lang', None) is not None:
            task.lang = str(payload.lang or '').strip() or task.lang
        if getattr(payload, 'scene', None) is not None:
            task.scene = str(payload.scene or '').strip() or task.scene
        if getattr(payload, 'dataset', None) is not None:
            task.dataset = str(payload.dataset or '').strip() or task.dataset
        if getattr(payload, 'problem_text', None) is not None:
            problem_text = str(payload.problem_text or '').strip()
            if not problem_text:
                raise ValueError('题目描述不能为空')
            task.problem_text = problem_text
        if getattr(payload, 'max_round', None) is not None:
            task.max_round = int(payload.max_round)
        if getattr(payload, 'is_trace_on', None) is not None:
            task.is_trace_on = bool(payload.is_trace_on)
        if getattr(payload, 'is_lesson_on', None) is not None:
            task.is_lesson_on = bool(payload.is_lesson_on)

        return save_task(db, task)

    def gen_init(self, db: Session, task_id: int, *, auto_gen_cases: bool = False, case_cfg: dict | None = None):
        return self.gen_svc.gen_init_code(db, task_id, auto_gen_cases=auto_gen_cases, case_cfg=case_cfg or {})

    def run_latest(self, db: Session, task_id: int):
        task = get_task(db, task_id)
        if not task:
            raise ValueError("任务不存在")
        cases = list_cases(db, task_id)
        ver = get_latest_version(db, task_id)
        if not ver:
            raise ValueError("请先生成初始代码")
        task.status = "running"
        db.commit()
        run = self.run_svc.run_version(
            db,
            task_id,
            ver.id,
            task.cur_round,
            self._normalize_version_code(db, ver),
            trace_on=bool(task.is_trace_on),
            problem_text=task.problem_text or "",
            inst_sugg="",
            scene=task.scene or 'func',
        )
        # 单次运行也要把首个版本登记为真实基线，但仅严格提升时刷新最佳版本。
        self.rb_svc.sync_best(db, task, ver.id, run.score)
        task.status = "pass" if run.result == "pass" else "fail"
        db.commit()
        return run

    def auto_fix(
        self,
        db: Session,
        task_id: int,
        max_round: int = 3,
        trace_on: bool | None = None,
        lesson_on: bool | None = None,
        stop_on_pass: bool | None = None,
        allow_rollback: bool = True,
    ):
        task = get_task(db, task_id)
        if not task:
            raise ValueError("任务不存在")
        cases = list_cases(db, task_id)

        eff_trace_on = bool(task.is_trace_on) if trace_on is None else bool(trace_on)
        eff_lesson_on = bool(task.is_lesson_on) if lesson_on is None else bool(lesson_on)
        eff_stop_on_pass = True if stop_on_pass is None else bool(stop_on_pass)

        task.max_round = max_round
        task.is_trace_on = eff_trace_on
        task.is_lesson_on = eff_lesson_on
        task.status = "running"
        db.commit()

        cur_ver = get_latest_version(db, task_id)
        if not cur_ver:
            cur_ver = self.gen_svc.gen_init_code(db, task_id)

        final_run = None
        last_inst_sugg = ""
        last_action = "continue"
        last_action_reason = ""
        rollback_ver_id = None
        stagnation_cnt = 0
        previous_score = float(task.best_score) if task.best_ver_id is not None else None
        last_tested_ver_id = cur_ver.id if cur_ver else None

        try:
            for round_no in range(1, max_round + 1):
                if self._stop_requested(db, task):
                    final_run = None
                    last_action = "stop"
                    last_action_reason = "用户请求中止任务；在进入下一轮前停止。"
                    break

                task.cur_round = round_no
                db.commit()

                final_run = self.run_svc.run_version(
                    db=db,
                    task_id=task_id,
                    ver_id=cur_ver.id,
                    round_no=round_no,
                    code_text=self._normalize_version_code(db, cur_ver),
                    trace_on=eff_trace_on,
                    problem_text=task.problem_text or "",
                    inst_sugg=last_inst_sugg,
                    scene=task.scene or "func",
                )
                last_tested_ver_id = cur_ver.id

                if self._stop_requested(db, task):
                    task.status = "stop"
                    db.commit()
                    last_action = "stop"
                    last_action_reason = "用户请求中止任务；当前执行轮完成后停止，未继续生成修复版本。"
                    break

                decision = self.rb_svc.decide(
                    task=task,
                    attempted_score=final_run.score,
                    previous_score=previous_score,
                    stagnation_cnt=stagnation_cnt,
                )
                if not allow_rollback and decision.action == "rollback":
                    decision = RollbackDecision(
                        action="continue",
                        reason="当前实验方案未启用 rollback；保留当前版本继续按错误反馈修复。",
                        stagnation_cnt=decision.stagnation_cnt,
                    )
                last_action = decision.action
                last_action_reason = decision.reason
                stagnation_cnt = decision.stagnation_cnt

                if decision.action == "accept":
                    self.rb_svc.sync_best(db, task, cur_ver.id, final_run.score)

                if final_run.result == "pass":
                    self.rb_svc.sync_best(db, task, cur_ver.id, final_run.score)
                    task.status = "pass"
                    db.commit()
                    if eff_stop_on_pass:
                        return {
                            "task_id": task.id,
                            "status": task.status,
                            "cur_round": task.cur_round,
                            "best_ver_id": task.best_ver_id,
                            "last_run_id": final_run.id,
                            "last_ver_id": cur_ver.id,
                            "last_action": last_action,
                            "last_action_reason": last_action_reason,
                            "rollback_ver_id": rollback_ver_id,
                            "trace_on": eff_trace_on,
                            "lesson_on": eff_lesson_on,
                            "stop_on_pass": eff_stop_on_pass,
                            "allow_rollback": allow_rollback,
                            "stopped_reason": "pass_and_stop_on_pass",
                        }
                    last_action = "accept"
                    last_action_reason = "已通过测试；stop_on_pass=False，跳出循环后统一返回。"
                    break

                err_text = final_run.tb_text or final_run.err_msg or "unknown error"
                trace_sum = final_run.trace_sum or ""

                plan = self.plan_svc.build_plan(
                    db=db,
                    task_id=task.id,
                    run_id=final_run.id,
                    round_no=round_no,
                    problem_text=task.problem_text,
                    code_text=self._normalize_version_code(db, cur_ver),
                    err_text=err_text,
                    trace_sum=trace_sum,
                    lesson_on=eff_lesson_on,
                    scene=task.scene or "func",
                )
                last_inst_sugg = (plan.inst_sugg or "") if eff_trace_on else ""

                if eff_lesson_on:
                    self.lesson_svc.save_lesson(
                        db=db,
                        task_id=task.id,
                        round_no=round_no,
                        run_id=final_run.id,
                        plan_id=plan.id,
                        err_text=err_text,
                        fix_plan=plan.fix_plan or "",
                        pass_cnt=final_run.pass_cnt,
                        total_cnt=final_run.total_cnt,
                        rollback_flag=(decision.action == "rollback"),
                    )

                base_ver = cur_ver
                if decision.action == "rollback" and task.best_ver_id:
                    best_ver = db.get(CodeVersion, task.best_ver_id)
                    if best_ver:
                        rollback_ver = self.rb_svc.make_rollback_version(
                            db=db,
                            task_id=task.id,
                            rollback_to=best_ver,
                            from_ver_id=cur_ver.id,
                            next_ver_no=len(list_versions(db, task_id)) + 1,
                            note=(
                                f"第{round_no}轮回退：当前版本 v{cur_ver.ver_no} 得分 {final_run.score:.3f}，"
                                f"切回最佳基线 v{best_ver.ver_no}"
                            ),
                        )
                        base_ver = rollback_ver
                        rollback_ver_id = rollback_ver.id

                fix_result = self.fix_svc.create_fix_version(
                    db=db,
                    task_id=task.id,
                    parent_ver_id=base_ver.id,
                    next_ver_no=len(list_versions(db, task_id)) + 1,
                    problem_text=task.problem_text,
                    code_text=base_ver.code_text,
                    fix_plan=plan.fix_plan or "请结合题意检查代码逻辑",
                    err_text=err_text,
                    trace_sum=trace_sum,
                    scene=task.scene or "func",
                    lesson_on=eff_lesson_on,
                    title=task.title or '',
                )
                cur_ver = fix_result.ver
                if fix_result.degraded:
                    task.status = "fail"
                    db.commit()
                    return {
                        "task_id": task.id,
                        "status": task.status,
                        "cur_round": task.cur_round,
                        "best_ver_id": task.best_ver_id,
                        "last_run_id": final_run.id if final_run else None,
                        "last_ver_id": cur_ver.id if cur_ver else None,
                        "last_action": "repair_error",
                        "last_action_reason": "修复代理未能生成可接受的新代码，已保留当前基线代码并停止后续轮次。",
                        "rollback_ver_id": rollback_ver_id,
                        "trace_on": eff_trace_on,
                        "lesson_on": eff_lesson_on,
                        "stop_on_pass": eff_stop_on_pass,
                        "allow_rollback": allow_rollback,
                        "stopped_reason": "repair_generation_failed",
                        "repair_error": fix_result.repair_error,
                        "repair_source": fix_result.repair_source,
                    }

                previous_score = final_run.score

            if task.status not in {"pass", "stop"} and cur_ver and last_tested_ver_id != cur_ver.id:
                # 兜底校验：最后一轮可能刚刚生成了一个新的 repair 版本，旧逻辑会在它
                # 还没被执行验证前就直接把任务判成 fail。这会把“最后一次修复其实已
                # 经成功”的场景错误地记成失败，尤其容易误导实验统计与 lesson。
                final_verify = self.run_svc.run_version(
                    db=db,
                    task_id=task_id,
                    ver_id=cur_ver.id,
                    round_no=task.cur_round,
                    code_text=self._normalize_version_code(db, cur_ver),
                    trace_on=eff_trace_on,
                    problem_text=task.problem_text or "",
                    inst_sugg=last_inst_sugg,
                    scene=task.scene or "func",
                )
                final_run = final_verify
                last_tested_ver_id = cur_ver.id
                if task.best_ver_id is None or float(final_verify.score or 0) > float(task.best_score or 0):
                    self.rb_svc.sync_best(db, task, cur_ver.id, final_verify.score)
                if final_verify.result == "pass":
                    task.status = "pass"
                    last_action = "accept"
                    last_action_reason = "最后一轮生成的修复版本在收尾校验中通过，已更新为最终结果。"
                else:
                    task.status = "fail"
                    last_action_reason = "最后一轮生成的修复版本已完成收尾校验，但仍未通过全部测试。"
            elif task.status not in {"pass", "stop"}:
                task.status = "fail"
            db.commit()
            return {
                "task_id": task.id,
                "status": task.status,
                "cur_round": task.cur_round,
                "best_ver_id": task.best_ver_id,
                "last_run_id": final_run.id if final_run else None,
                "last_ver_id": cur_ver.id if cur_ver else None,
                "last_action": last_action,
                "last_action_reason": last_action_reason,
                "rollback_ver_id": rollback_ver_id,
                "trace_on": eff_trace_on,
                "lesson_on": eff_lesson_on,
                "stop_on_pass": eff_stop_on_pass,
                "allow_rollback": allow_rollback,
                "stopped_reason": (
                    "pass_reached_but_continue_return" if task.status == "pass"
                    else "stop_requested" if task.status == "stop"
                    else "max_round_reached"
                ),
            }
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            task = get_task(db, task_id)
            if task:
                task.status = "fail"
                try:
                    save_task(db, task)
                except Exception:
                    db.rollback()
            raise RuntimeError(f"自动修复中断：{exc}") from exc

