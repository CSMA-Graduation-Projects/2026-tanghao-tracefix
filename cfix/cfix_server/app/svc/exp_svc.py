"""实验服务，负责封装对应业务域的核心流程。"""

from __future__ import annotations

from types import SimpleNamespace
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from app.data.bench_bank import get_dataset_size, get_exp_problems
from app.data.exp_profile_store import get_profile_by_key, get_profile_for_exp, list_profiles as list_exp_profiles_store, save_profile_for_exp
from app.db.sess import SessionLocal
from app.models.exp import Experiment, ExperimentItem
from app.repo.exp_repo import (
    add_exp_item,
    clear_exp_items,
    create_exp,
    get_exp,
    get_exp_owned,
    list_exp_items,
    list_exps,
    save_exp,
)
from app.repo.task_repo import get_task, list_case_results, list_runs, list_trace, list_versions
from app.svc.task_svc import TaskService
from app.svc.model_svc import resolve_default_model_id
from app.utils.case_pack import build_typical_cases
from app.utils.ch4 import build_ch4_metrics, build_compare_rows, build_compare_summary, build_single_chart


class ExpService:
    """实验服务。

    通过轻量后台线程运行整批实验，避免 /exp/{id}/start 请求本身阻塞。
    前端只需要轮询实验详情或列表，即可获得真实进度与最终结果。
    """

    _lock = threading.Lock()
    _threads: dict[int, threading.Thread] = {}
    _job_meta: dict[int, dict] = {}

    def __init__(self):
        self.task_svc = TaskService()

    def list_profiles(self) -> list[dict]:
        return list_exp_profiles_store()

    def get_profile_info(self, exp_id: int | None = None, profile_key: str | None = None) -> dict:
        if exp_id is not None:
            return get_profile_for_exp(exp_id)
        return get_profile_by_key(profile_key)

    def _utc_now_text(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _set_job_meta(self, exp_id: int, **kwargs):
        with self._lock:
            meta = dict(self._job_meta.get(exp_id) or {})
            meta.update(kwargs)
            if "logs" not in meta:
                meta["logs"] = []
            self._job_meta[exp_id] = meta
            return dict(meta)

    @staticmethod
    def _is_quota_exhausted_error(exc: Exception | str) -> bool:
        s = str(exc or '').lower()
        markers = (
            'free tier of the model has been exhausted', 'quota', '额度', 'exhausted',
            '余额不足', 'insufficient_quota', 'rate limit reached for requests',
        )
        return any(m in s for m in markers)

    @staticmethod
    def _is_generation_stage_failure(task) -> bool:
        return task is None

    def _append_job_log(self, exp_id: int, text: str, level: str = "info", **extra):
        with self._lock:
            meta = dict(self._job_meta.get(exp_id) or {})
            logs = list(meta.get("logs") or [])
            item = {
                "ts": self._utc_now_text(),
                "level": level,
                "text": text,
            }
            item.update({k: v for k, v in extra.items() if v is not None})
            logs.append(item)
            meta["logs"] = logs[-80:]
            self._job_meta[exp_id] = meta
            return list(meta["logs"])

    def _get_job_meta(self, exp_id: int) -> dict:
        with self._lock:
            meta = dict(self._job_meta.get(exp_id) or {})
            meta["logs"] = list(meta.get("logs") or [])
            return meta

    def list_exp(self, db: Session, user_id: int):
        return list_exps(db, user_id)

    def get_exp(self, db: Session, user_id: int, exp_id: int):
        return get_exp_owned(db, exp_id, user_id)

    def is_running(self, exp_id: int) -> bool:
        with self._lock:
            th = self._threads.get(exp_id)
            return bool(th and th.is_alive())

    def launch_exp_job(self, exp_id: int) -> bool:
        """启动后台实验线程。

        返回 True 表示本次真正创建了新线程；False 表示已有线程正在执行。
        """
        with self._lock:
            old = self._threads.get(exp_id)
            if old and old.is_alive():
                return False
            th = threading.Thread(
                target=self.run_exp_job,
                args=(exp_id,),
                daemon=True,
                name=f"exp-job-{exp_id}",
            )
            self._threads[exp_id] = th
            th.start()
            return True

    def create_exp(self, db: Session, user_id: int, payload):
        dataset = payload.dataset
        dataset_size = max(1, int(get_dataset_size(dataset)))
        sample_cnt = max(1, min(int(payload.sample_cnt or 1), dataset_size))
        profile = get_profile_by_key(getattr(payload, 'profile_key', None))
        raw_max_round = int(payload.max_round or 1)
        max_round = 1 if not profile.get('iterative') else max(1, raw_max_round)
        model_id = payload.model_id if getattr(payload, 'model_id', None) is not None else resolve_default_model_id(db, user_id)
        exp = Experiment(
            user_id=user_id,
            name=payload.name,
            dataset=dataset,
            model_id=model_id,
            sample_cnt=sample_cnt,
            max_round=max_round,
            status="draft",
        )
        row = create_exp(db, exp)
        save_profile_for_exp(row.id, profile.get('key'))
        return row

    def start_exp(self, db: Session, user_id: int, exp_id: int):
        exp = get_exp_owned(db, exp_id, user_id)
        if not exp:
            raise ValueError("实验不存在或无权访问")
        clear_exp_items(db, exp.id)
        dataset_size = max(1, int(get_dataset_size(exp.dataset)))
        exp.sample_cnt = max(1, min(int(exp.sample_cnt or 1), dataset_size))
        exp.status = "running"
        save_exp(db, exp)
        profile = get_profile_for_exp(exp.id)
        self._set_job_meta(
            exp.id,
            phase="queued",
            current_problem_no=None,
            current_problem_title="",
            current_task_id=None,
            current_index=0,
            total=int(exp.sample_cnt or 0),
            logs=[],
        )
        self._append_job_log(exp.id, f"实验已进入后台队列，等待执行（方案：{profile.get('short_label') or profile.get('label')}）")
        return exp

    def stop_exp(self, db: Session, user_id: int, exp_id: int):
        exp = get_exp_owned(db, exp_id, user_id)
        if not exp:
            raise ValueError("实验不存在或无权访问")
        exp.status = "stop"
        self._append_job_log(exp.id, "收到停止请求，当前题结束后停止后续样本", level="warning")
        self._set_job_meta(exp.id, phase="stopping")
        return save_exp(db, exp)

    def run_exp_job(self, exp_id: int):
        try:
            with SessionLocal() as db:
                exp = get_exp(db, exp_id)
                if not exp:
                    return

                exp.status = "running"
                save_exp(db, exp)
                profile = get_profile_for_exp(exp.id)

                problems = get_exp_problems(exp.dataset, exp.sample_cnt)
                total = len(problems)
                self._set_job_meta(exp.id, phase="running", total=total, current_index=0, current_task_id=None, profile_key=profile.get('key'))
                self._append_job_log(exp.id, f"实验开始，共 {total} 题；方案：{profile.get('label')}（Trace={'开' if profile.get('trace_on') else '关'}，Lesson={'开' if profile.get('lesson_on') else '关'}，Rollback={'开' if profile.get('rollback_on') else '关'}）")
                if not problems:
                    exp.status = "fail"
                    save_exp(db, exp)
                    self._set_job_meta(exp.id, phase="fail")
                    self._append_job_log(exp.id, "未读取到可用实验题目", level="error")
                    return

                final_pass_all = True

                for idx, item in enumerate(problems, start=1):
                    db.refresh(exp)
                    if exp.status == "stop":
                        self._set_job_meta(exp.id, phase="stop", current_index=idx - 1)
                        self._append_job_log(exp.id, f"实验已停止，已完成 {idx - 1}/{total} 题", level="warning")
                        break

                    self._set_job_meta(
                        exp.id,
                        phase="running",
                        current_problem_no=int(item["problem_no"]),
                        current_problem_title=item.get("title", ""),
                        current_task_id=None,
                        current_index=idx,
                        total=total,
                    )
                    self._append_job_log(
                        exp.id,
                        f"开始执行第 {idx}/{total} 题（题号 {int(item['problem_no'])}）：{item.get('title', '')}",
                        problem_no=int(item["problem_no"]),
                        problem_title=item.get("title", ""),
                        current_index=idx,
                        total=total,
                        action="problem_start",
                    )

                    task_payload = SimpleNamespace(
                        sess_id=None,
                        model_id=exp.model_id,
                        title=f"[EXP {exp.id}] {item['title']}",
                        lang="python",
                        scene=item.get("scene", "func"),
                        dataset=exp.dataset,
                        problem_text=item["problem_text"],
                        max_round=exp.max_round,
                        is_trace_on=bool(profile.get('trace_on')),
                        is_lesson_on=bool(profile.get('lesson_on')),
                        cases=[SimpleNamespace(**case) for case in item.get("cases", [])],
                    )

                    task = None
                    try:
                        task = self.task_svc.create_new_task(db, exp.user_id, task_payload)
                        self._set_job_meta(exp.id, current_task_id=task.id)
                        self._append_job_log(
                            exp.id,
                            f"已创建任务 #{task.id}，开始生成初始代码",
                            task_id=task.id,
                            problem_no=int(item["problem_no"]),
                            problem_title=item.get("title", ""),
                            current_index=idx,
                            total=total,
                            action="task_created",
                        )
                        self.task_svc.gen_init(db, task.id)
                        init_run = self.task_svc.run_latest(db, task.id)

                        init_pass = init_run.result == "pass"
                        self._append_job_log(
                            exp.id,
                            f"初始执行结果：{'通过' if init_pass else '失败'}（{int(init_run.pass_cnt or 0)}/{int(init_run.total_cnt or 0)}）",
                            task_id=task.id,
                            problem_no=int(item["problem_no"]),
                            problem_title=item.get("title", ""),
                            pass_cnt=int(init_run.pass_cnt or 0),
                            total_cnt=int(init_run.total_cnt or 0),
                            action="init_run",
                        )
                        final_pass = init_pass
                        repair_ok = False
                        round_used = 0

                        if not init_pass and bool(profile.get('iterative')):
                            db.refresh(exp)
                            if exp.status == "stop":
                                break

                            self._append_job_log(
                                exp.id,
                                f"进入自动修复，最大轮次 {int(exp.max_round or 0)}；方案：{profile.get('short_label')}",
                                task_id=task.id,
                                problem_no=int(item["problem_no"]),
                                problem_title=item.get("title", ""),
                                action="auto_fix_start",
                            )
                            auto_rs = self.task_svc.auto_fix(
                                db=db,
                                task_id=task.id,
                                max_round=exp.max_round,
                                trace_on=bool(profile.get('trace_on')),
                                lesson_on=bool(profile.get('lesson_on')),
                                stop_on_pass=True,
                                allow_rollback=bool(profile.get('rollback_on')),
                            )
                            final_pass = auto_rs.get("status") == "pass"
                            repair_ok = final_pass and (not init_pass)
                            round_used = int(auto_rs.get("cur_round") or 0)
                            self._append_job_log(
                                exp.id,
                                f"自动修复结束：{'通过' if final_pass else '未通过'}，已用轮次 {round_used}",
                                task_id=task.id,
                                problem_no=int(item["problem_no"]),
                                problem_title=item.get("title", ""),
                                round_used=int(round_used),
                                action="auto_fix_done",
                            )
                        elif not init_pass:
                            self._append_job_log(
                                exp.id,
                                "当前实验方案为无反馈单轮生成：初始代码测试失败后不再进入自动修复。",
                                task_id=task.id,
                                problem_no=int(item["problem_no"]),
                                problem_title=item.get("title", ""),
                                action="single_pass_only",
                            )

                        total_time_ms = sum(int(x.time_ms or 0) for x in list_runs(db, task.id))
                        if not final_pass:
                            final_pass_all = False

                        add_exp_item(
                            db,
                            ExperimentItem(
                                exp_id=exp.id,
                                task_id=task.id,
                                problem_no=int(item["problem_no"]),
                                init_pass=bool(init_pass),
                                final_pass=bool(final_pass),
                                repair_ok=bool(repair_ok),
                                round_used=int(round_used),
                                time_ms=int(total_time_ms),
                            ),
                        )
                        self._append_job_log(
                            exp.id,
                            f"第 {idx}/{total} 题完成：{'最终通过' if final_pass else '最终失败'}，耗时 {int(total_time_ms)} ms",
                            task_id=task.id,
                            problem_no=int(item["problem_no"]),
                            problem_title=item.get("title", ""),
                            final_pass=bool(final_pass),
                            time_ms=int(total_time_ms),
                            action="problem_done",
                        )
                    except Exception as prob_exc:  # noqa: BLE001
                        db.rollback()
                        final_pass_all = False
                        quota_exhausted = self._is_quota_exhausted_error(prob_exc)
                        if task is not None:
                            try:
                                db.refresh(task)
                            except Exception:
                                pass
                            try:
                                task.status = "fail"
                                db.add(task)
                                db.commit()
                            except Exception:
                                db.rollback()
                            total_time_ms = sum(int(x.time_ms or 0) for x in list_runs(db, task.id))
                            add_exp_item(
                                db,
                                ExperimentItem(
                                    exp_id=exp.id,
                                    task_id=task.id,
                                    problem_no=int(item["problem_no"]),
                                    init_pass=False,
                                    final_pass=False,
                                    repair_ok=False,
                                    round_used=0,
                                    time_ms=int(total_time_ms),
                                ),
                            )
                        log_text = f"第 {idx}/{total} 题异常失败：{prob_exc}"
                        if quota_exhausted:
                            log_text = f"第 {idx}/{total} 题因模型额度耗尽而停止实验：{prob_exc}"
                        self._append_job_log(
                            exp.id,
                            log_text,
                            level="error",
                            task_id=(task.id if task is not None else None),
                            problem_no=int(item["problem_no"]),
                            problem_title=item.get("title", ""),
                            action=("quota_exhausted" if quota_exhausted else "problem_error"),
                        )
                        if quota_exhausted:
                            exp = get_exp(db, exp.id)
                            if exp:
                                exp.status = "fail"
                                save_exp(db, exp)
                            self._set_job_meta(
                                exp_id=exp.id,
                                phase="quota_exhausted",
                                current_problem_no=int(item["problem_no"]),
                                current_problem_title=item.get("title", ""),
                                current_task_id=(task.id if task is not None else None),
                                current_index=idx,
                                total=total,
                            )
                            self._append_job_log(exp.id, "检测到模型额度耗尽，实验提前停止，避免后续样本全部空跑。", level="warning", action="quota_stop")
                            break
                        continue

                db.refresh(exp)
                if exp.status != "stop":
                    exp.status = "pass" if final_pass_all else "fail"
                    save_exp(db, exp)
                    self._set_job_meta(
                        exp.id,
                        phase=exp.status,
                        current_problem_no=None,
                        current_problem_title="",
                        current_task_id=None,
                        current_index=len(list_exp_items(db, exp.id)),
                        total=total,
                    )
                    self._append_job_log(exp.id, f"实验结束，最终状态：{exp.status}")
        except Exception as e:
            with SessionLocal() as db:
                exp = get_exp(db, exp_id)
                if exp and exp.status != "stop":
                    exp.status = "fail"
                    save_exp(db, exp)
            self._set_job_meta(exp_id, phase="fail")
            self._append_job_log(exp_id, f"实验异常终止：{e}", level="error")
            raise
        finally:
            with self._lock:
                self._threads.pop(exp_id, None)

    def _items_view(self, db: Session, exp_id: int) -> list[dict]:
        rows = list_exp_items(db, exp_id)
        data: list[dict] = []
        for x in rows:
            task = get_task(db, x.task_id)
            runs = list_runs(db, x.task_id)
            versions = list_versions(db, x.task_id)
            last_run = runs[0] if runs else None
            failed_runs = [item for item in runs if item.result != "pass"]
            latest_failed_run = failed_runs[0] if failed_runs else None
            err_type = "-" if x.final_pass else (((latest_failed_run or last_run).err_type if (latest_failed_run or last_run) else None) or "WrongAnswer")
            rollback_cnt = sum(1 for item in versions if (item.ver_type or "") == "rollback")
            has_rollback = rollback_cnt > 0
            latest_ver = versions[-1] if versions else None
            init_ver = versions[0] if versions else None
            latest_trace_sum = ""
            latest_trace_preview = []
            latest_failed_cases = []
            target_run = latest_failed_run or last_run
            if target_run:
                latest_trace_sum = (target_run.trace_sum or "").strip()
                trace_rows = list_trace(db, target_run.id)
                latest_trace_preview = [
                    {
                        "seq_no": item.seq_no,
                        "node_type": item.node_type,
                        "func_name": item.func_name,
                        "var_name": item.var_name,
                        "line_no": item.line_no,
                        "log_text": item.log_text,
                    }
                    for item in trace_rows[:12]
                ]
                case_rows = list_case_results(db, target_run.id)
                latest_failed_cases = [
                    {
                        "case_id": item.case_id,
                        "result": item.result,
                        "actual_out": item.actual_out,
                        "err_msg": item.err_msg,
                        "time_ms": item.time_ms,
                    }
                    for item in case_rows
                    if (item.result or "") != "pass"
                ]

            typical_tags: list[str] = []
            if bool(x.repair_ok):
                typical_tags.append("修复贡献案例")
            if has_rollback and bool(x.final_pass):
                typical_tags.append("rollback 生效案例")
            if not bool(x.final_pass):
                typical_tags.append("最终失败案例")

            data.append(
                {
                    "problem_no": x.problem_no,
                    "task_id": x.task_id,
                    "title": task.title if task else f"题目 {x.problem_no}",
                    "init_pass": bool(x.init_pass),
                    "final_pass": bool(x.final_pass),
                    "repair_ok": bool(x.repair_ok),
                    "final_failed": not bool(x.final_pass),
                    "round_used": x.round_used,
                    "time_ms": x.time_ms,
                    "err_type": err_type,
                    "latest_run_id": last_run.id if last_run else None,
                    "latest_failed_run_id": latest_failed_run.id if latest_failed_run else None,
                    "latest_result": last_run.result if last_run else None,
                    "latest_trace_sum": latest_trace_sum,
                    "latest_trace_preview": latest_trace_preview,
                    "latest_failed_cases": latest_failed_cases,
                    "rollback_cnt": rollback_cnt,
                    "has_rollback": has_rollback,
                    "typical_tags": typical_tags,
                    "best_ver_id": task.best_ver_id if task else None,
                    "best_score": task.best_score if task else 0,
                    "latest_ver_id": latest_ver.id if latest_ver else None,
                    "init_ver_id": init_ver.id if init_ver else None,
                }
            )
        return data

    def report(self, db: Session, user_id: int, exp_id: int) -> dict:
        exp = get_exp_owned(db, exp_id, user_id)
        if not exp:
            raise ValueError("实验不存在或无权访问")

        items = self._items_view(db, exp.id)
        total = len(items)
        if total == 0:
            empty_report = {
                "dataset": exp.dataset,
                "sample_cnt": int(exp.sample_cnt or 0),
                "init_pass_rate": 0.0,
                "final_pass_rate": 0.0,
                "repair_success_rate": 0.0,
                "avg_round": 0.0,
                "avg_time_ms": 0,
                "success_case_cnt": 0,
                "rollback_case_cnt": 0,
                "final_fail_case_cnt": 0,
                "avg_rollback_cnt": 0.0,
                "typical_cases": {
                    "success_case": None,
                    "rollback_case": None,
                    "failure_case": None,
                },
                "case_type_dist": {
                    "repair_success": 0,
                    "rollback_effective": 0,
                    "final_failure": 0,
                    "ordinary": 0,
                },
                "available_case_cnt": 0,
            }
            empty_report["ch4"] = build_ch4_metrics(empty_report)
            return empty_report

        init_pass_cnt = sum(1 for x in items if x["init_pass"])
        final_pass_cnt = sum(1 for x in items if x["final_pass"])
        repair_cnt = sum(1 for x in items if x["repair_ok"])
        rollback_case_cnt = sum(1 for x in items if x.get("has_rollback"))
        final_fail_case_cnt = sum(1 for x in items if not x.get("final_pass"))
        avg_round = sum(float(x["round_used"] or 0) for x in items) / total
        avg_time_ms = sum(int(x["time_ms"] or 0) for x in items) / total
        avg_rollback_cnt = sum(int(x.get("rollback_cnt") or 0) for x in items) / total
        case_pack = build_typical_cases(items)
        report = {
            "dataset": exp.dataset,
            "sample_cnt": total,
            "init_pass_rate": round(init_pass_cnt / total, 4),
            "final_pass_rate": round(final_pass_cnt / total, 4),
            "repair_success_rate": round(repair_cnt / total, 4),
            "avg_round": round(avg_round, 2),
            "avg_time_ms": int(avg_time_ms),
            "success_case_cnt": repair_cnt,
            "rollback_case_cnt": rollback_case_cnt,
            "final_fail_case_cnt": final_fail_case_cnt,
            "avg_rollback_cnt": round(avg_rollback_cnt, 2),
            "typical_cases": {
                "success_case": case_pack.get("success_case"),
                "rollback_case": case_pack.get("rollback_case"),
                "failure_case": case_pack.get("failure_case"),
            },
            "case_type_dist": case_pack.get("case_type_dist") or {},
            "available_case_cnt": int(case_pack.get("available_case_cnt") or 0),
        }
        report["ch4"] = build_ch4_metrics(report)
        return report

    def chart(self, db: Session, user_id: int, exp_id: int) -> dict:
        exp = get_exp_owned(db, exp_id, user_id)
        if not exp:
            raise ValueError("实验不存在或无权访问")

        items = self._items_view(db, exp.id)
        report = self.report(db, user_id, exp.id)
        err_map: dict[str, int] = {}
        for x in items:
            key = "通过" if x["final_pass"] else (x.get("err_type") or "未知")
            err_map[key] = err_map.get(key, 0) + 1
        error_dist = [{"name": k, "count": v} for k, v in sorted(err_map.items(), key=lambda t: (-t[1], t[0]))]
        chart = {
            "pass_compare": [
                {"label": "初始通过率", "value": report["init_pass_rate"]},
                {"label": "最终通过率", "value": report["final_pass_rate"]},
            ],
            "repair_success_rate": report["repair_success_rate"],
            "avg_round": report["avg_round"],
            "avg_time_ms": report["avg_time_ms"],
            "error_dist": error_dist,
            "case_type_dist": report.get("case_type_dist") or {},
        }
        chart["ch4"] = build_single_chart(
            report=report,
            error_dist=error_dist,
            case_type_dist=report.get("case_type_dist") or {},
        )
        return chart

    def items(self, db: Session, user_id: int, exp_id: int) -> list[dict]:
        exp = get_exp_owned(db, exp_id, user_id)
        if not exp:
            raise ValueError("实验不存在或无权访问")
        return self._items_view(db, exp.id)


    def compare(self, db: Session, user_id: int, exp_ids: list[int]) -> dict:
        ids = []
        for item in exp_ids:
            try:
                num = int(item)
            except Exception:
                continue
            if num not in ids:
                ids.append(num)
        if len(ids) < 2 or len(ids) > 3:
            raise ValueError("实验对比需要选择 2 到 3 个实验")

        exps = []
        for exp_id in ids:
            exp = get_exp_owned(db, exp_id, user_id)
            if not exp:
                raise ValueError(f"实验 {exp_id} 不存在或无权访问")
            report = self.report(db, user_id, exp_id)
            chart = self.chart(db, user_id, exp_id)
            profile = get_profile_for_exp(exp_id)
            exps.append({
                'id': exp.id,
                'name': exp.name,
                'dataset': exp.dataset,
                'sample_cnt': exp.sample_cnt,
                'max_round': exp.max_round,
                'status': exp.status,
                'profile': profile,
                'report': report,
                'chart': chart,
            })

        mode_rows = []
        for item in exps:
            rep = item['report'] or {}
            mode_rows.append({
                'exp_id': item['id'],
                'mode': item['profile'].get('key'),
                'label': f"{item['name']}（{item['profile'].get('short_label') or item['profile'].get('label')}）",
                'sample_cnt': rep.get('sample_cnt') or item.get('sample_cnt') or 0,
                'init_pass_rate': rep.get('init_pass_rate') or 0.0,
                'final_pass_rate': rep.get('final_pass_rate') or 0.0,
                'repair_success_rate': rep.get('repair_success_rate') or 0.0,
                'avg_round': rep.get('avg_round') or 0.0,
                'avg_time_ms': rep.get('avg_time_ms') or 0,
            })

        compare_pack = build_compare_rows(mode_rows)
        compare_summary = compare_pack.get('summary') or build_compare_summary(mode_rows)
        metric_specs = [
            ('final_pass_rate', '最终通过率', 'high'),
            ('repair_success_rate', '修复贡献率', 'high'),
            ('delta_pass_rate', '通过率提升', 'high'),
            ('avg_round', '平均修复轮次', 'low'),
            ('avg_time_ms', '平均耗时(ms)', 'low'),
        ]

        def _build_rank_text(items: list[dict]) -> str:
            if not items:
                return '-'
            groups = []
            for item in items:
                value = float(item.get('value') or 0)
                if groups and abs(float(groups[-1]['value']) - value) < 1e-9:
                    groups[-1]['labels'].append(item.get('label') or '-')
                else:
                    groups.append({'value': value, 'labels': [item.get('label') or '-']})
            return ' > '.join(' = '.join(group['labels']) for group in groups)

        metric_rows = []
        for key, label, prefer in metric_specs:
            values = []
            for item in exps:
                rep = item.get('report') or {}
                if key == 'delta_pass_rate':
                    value = float(rep.get('final_pass_rate') or 0.0) - float(rep.get('init_pass_rate') or 0.0)
                else:
                    value = rep.get(key) or 0
                values.append({
                    'exp_id': item['id'],
                    'label': item['name'],
                    'value': value,
                })
            ordered = sorted(values, key=lambda x: float(x.get('value') or 0), reverse=(prefer == 'high'))
            best_value = float(ordered[0].get('value') or 0) if ordered else 0.0
            best_names = [x.get('label') or '-' for x in ordered if abs(float(x.get('value') or 0) - best_value) < 1e-9]
            best_label = '持平' if len(best_names) == len(values) else ' / '.join(best_names)
            metric_rows.append({
                'metric_key': key,
                'metric_label': label,
                'prefer': prefer,
                'values': [
                    {
                        'exp_id': item['exp_id'],
                        'label': item['label'],
                        'value': item['value'],
                        'text': next((g_item.get('text') for g in (compare_pack.get('groups') or []) if g.get('metric_key') == key for g_item in (g.get('items') or []) if int(g_item.get('exp_id') or 0) == int(item['exp_id'])), str(item['value'])),
                    }
                    for item in values
                ],
                'best_label': best_label,
                'rank_text': _build_rank_text(ordered),
            })

        return {
            'experiments': exps,
            'compare': compare_pack,
            'summary': compare_summary,
            'metric_rows': metric_rows,
        }

    def progress(self, db: Session, user_id: int, exp_id: int) -> dict:
        exp = get_exp_owned(db, exp_id, user_id)
        if not exp:
            raise ValueError("实验不存在或无权访问")
        done = len(list_exp_items(db, exp.id))
        meta = self._get_job_meta(exp.id)
        meta_total = meta.get("total")
        total = max(1, int(meta_total if meta_total is not None else (exp.sample_cnt or 0)))
        if exp.status in {"pass", "fail", "stop"} and done > 0:
            pct = 100
        elif exp.status == "running":
            pct = min(99, int(done / total * 100))
        else:
            pct = 0
        cur_problem_no = meta.get("current_problem_no")
        cur_problem_title = meta.get("current_problem_title") or ""
        cur_index = int(meta.get("current_index") or 0)
        cur_task_id = meta.get("current_task_id")
        phase = meta.get("phase") or exp.status
        if exp.status == "draft":
            text = "待启动"
        elif exp.status == "running":
            if cur_problem_no is not None:
                text = f"运行中（{done}/{total}），当前第 {cur_index}/{total} 题：#{cur_problem_no}"
            else:
                text = f"运行中（{done}/{total}）"
        elif exp.status == "stop":
            text = f"已停止（{done}/{total}）"
        else:
            text = f"已完成（{done}/{total}）"
        return {
            "progress": pct,
            "progress_text": text,
            "phase": phase,
            "current_problem_no": cur_problem_no,
            "current_problem_title": cur_problem_title,
            "current_index": cur_index,
            "current_task_id": cur_task_id,
            "total": total,
            "logs": meta.get("logs") or [],
        }

