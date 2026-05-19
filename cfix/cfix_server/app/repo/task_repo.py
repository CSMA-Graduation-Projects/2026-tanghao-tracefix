"""任务数据访问层，负责组织对应实体的数据库读写。"""

from __future__ import annotations

from sqlalchemy import delete, desc, select, update
from sqlalchemy.orm import Session

from app.models.case import TestCase
from app.models.chat import ChatSession
from app.models.exp import Experiment, ExperimentItem
from app.models.lesson import Lesson
from app.models.plan import RepairPlan
from app.models.run import CaseResult, RunRecord
from app.models.task import Task
from app.models.trace import TraceRecord
from app.models.ver import CodeVersion


# ===== chat =====
def get_chat_sess_owned(db: Session, sess_id: int, user_id: int) -> ChatSession | None:
    return db.execute(
        select(ChatSession).where(ChatSession.id == sess_id, ChatSession.user_id == user_id)
    ).scalar_one_or_none()


def update_chat_sess_title(db: Session, row: ChatSession, title: str) -> ChatSession:
    row.title = title
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ===== task =====
def create_task(db: Session, task: Task) -> Task:
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Task | None:
    return db.get(Task, task_id)


def get_task_owned(db: Session, task_id: int, user_id: int) -> Task | None:
    return db.execute(select(Task).where(Task.id == task_id, Task.user_id == user_id)).scalar_one_or_none()


def list_tasks_owned(db: Session, user_id: int):
    return db.execute(select(Task).where(Task.user_id == user_id).order_by(desc(Task.id))).scalars().all()


def save_task(db: Session, task: Task) -> Task:
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def stop_task_owned(db: Session, task_id: int, user_id: int) -> Task | None:
    task = get_task_owned(db, task_id, user_id)
    if not task:
        return None
    task.status = "stop"
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _task_run_ids(db: Session, task_id: int) -> list[int]:
    return [int(x) for x in db.execute(select(RunRecord.id).where(RunRecord.task_id == task_id)).scalars().all()]


def _task_plan_ids(db: Session, task_id: int) -> list[int]:
    return [int(x) for x in db.execute(select(RepairPlan.id).where(RepairPlan.task_id == task_id)).scalars().all()]


def delete_task_owned(db: Session, task_id: int, user_id: int) -> bool:
    task = get_task_owned(db, task_id, user_id)
    if not task:
        return False

    try:
        run_ids = _task_run_ids(db, task_id)
        plan_ids = _task_plan_ids(db, task_id)

        # 先解除容易引发完整性错误的“反向引用”关系，再删父表。
        if plan_ids:
            db.execute(
                update(Lesson)
                .where(Lesson.from_plan_id.in_(plan_ids))
                .values(from_plan_id=None)
            )
        if run_ids:
            db.execute(
                update(Lesson)
                .where(Lesson.from_run_id.in_(run_ids))
                .values(from_run_id=None)
            )

        # 先删除最下游依赖表。
        if run_ids:
            db.execute(delete(TraceRecord).where(TraceRecord.run_id.in_(run_ids)))
            db.execute(delete(CaseResult).where(CaseResult.run_id.in_(run_ids)))

        # 再删 lesson / plan。
        db.execute(delete(Lesson).where(Lesson.task_id == task_id))
        if run_ids:
            db.execute(delete(Lesson).where(Lesson.from_run_id.in_(run_ids)))
        if plan_ids:
            db.execute(delete(Lesson).where(Lesson.from_plan_id.in_(plan_ids)))

        db.execute(delete(RepairPlan).where(RepairPlan.task_id == task_id))

        # 与实验的关联记录必须先删。
        db.execute(delete(ExperimentItem).where(ExperimentItem.task_id == task_id))

        # 删除运行记录前，确保其下游已经被清理。
        if run_ids:
            db.execute(delete(RunRecord).where(RunRecord.id.in_(run_ids)))

        # 如果需要替换/删除任务用例，先删掉依赖这些用例的 case_res，避免 FK 冲突。
        db.execute(delete(TestCase).where(TestCase.task_id == task_id))

        # 版本表存在 self FK(parent_id)，删除前先置空。
        db.execute(update(CodeVersion).where(CodeVersion.task_id == task_id).values(parent_id=None))
        db.execute(delete(CodeVersion).where(CodeVersion.task_id == task_id))

        db.delete(task)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# ===== case =====
def add_case(db: Session, case: TestCase) -> TestCase:
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def add_case_batch(db: Session, rows: list[TestCase]):
    if not rows:
        return []
    db.add_all(rows)
    db.commit()
    return rows


def replace_cases(db: Session, task_id: int, rows: list[TestCase]):
    run_ids = _task_run_ids(db, task_id)
    try:
        # case_res 通过 case_id 依赖测试用例；若要替换整个任务的用例集合，
        # 需要先清理旧运行下的单用例结果，避免删除 cf_case 时触发 FK 冲突。
        if run_ids:
            db.execute(delete(CaseResult).where(CaseResult.run_id.in_(run_ids)))
        db.execute(delete(TestCase).where(TestCase.task_id == task_id))
        if rows:
            db.add_all(rows)
        db.commit()
        return rows
    except Exception:
        db.rollback()
        raise


def list_cases(db: Session, task_id: int):
    return db.execute(select(TestCase).where(TestCase.task_id == task_id).order_by(TestCase.sort_no, TestCase.id)).scalars().all()


# ===== version =====
def add_version(db: Session, ver: CodeVersion) -> CodeVersion:
    db.add(ver)
    db.commit()
    db.refresh(ver)
    return ver


def list_versions(db: Session, task_id: int):
    return db.execute(select(CodeVersion).where(CodeVersion.task_id == task_id).order_by(CodeVersion.ver_no, CodeVersion.id)).scalars().all()


def get_latest_version(db: Session, task_id: int) -> CodeVersion | None:
    return db.execute(select(CodeVersion).where(CodeVersion.task_id == task_id).order_by(desc(CodeVersion.ver_no), desc(CodeVersion.id))).scalars().first()


def get_ver_owned(db: Session, ver_id: int, user_id: int) -> CodeVersion | None:
    return db.execute(
        select(CodeVersion)
        .join(Task, Task.id == CodeVersion.task_id)
        .where(CodeVersion.id == ver_id, Task.user_id == user_id)
    ).scalar_one_or_none()


# ===== run =====
def add_run(db: Session, row: RunRecord) -> RunRecord:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_runs(db: Session, task_id: int):
    return db.execute(select(RunRecord).where(RunRecord.task_id == task_id).order_by(desc(RunRecord.id))).scalars().all()


def list_runs_owned(db: Session, task_id: int, user_id: int):
    return db.execute(
        select(RunRecord)
        .join(Task, Task.id == RunRecord.task_id)
        .where(RunRecord.task_id == task_id, Task.user_id == user_id)
        .order_by(desc(RunRecord.id))
    ).scalars().all()


def get_run_owned(db: Session, run_id: int, user_id: int) -> RunRecord | None:
    return db.execute(
        select(RunRecord)
        .join(Task, Task.id == RunRecord.task_id)
        .where(RunRecord.id == run_id, Task.user_id == user_id)
    ).scalar_one_or_none()


def add_case_result_batch(db: Session, rows: list[CaseResult]):
    if not rows:
        return []
    db.add_all(rows)
    db.commit()
    return rows


def list_case_results(db: Session, run_id: int):
    return db.execute(select(CaseResult).where(CaseResult.run_id == run_id).order_by(CaseResult.id)).scalars().all()


def add_trace_batch(db: Session, rows: list[TraceRecord]):
    if not rows:
        return []
    db.add_all(rows)
    db.commit()
    return rows


def list_trace(db: Session, run_id: int):
    return db.execute(select(TraceRecord).where(TraceRecord.run_id == run_id).order_by(TraceRecord.seq_no, TraceRecord.id)).scalars().all()


def list_trace_owned(db: Session, run_id: int, user_id: int):
    return db.execute(
        select(TraceRecord)
        .join(RunRecord, RunRecord.id == TraceRecord.run_id)
        .join(Task, Task.id == RunRecord.task_id)
        .where(TraceRecord.run_id == run_id, Task.user_id == user_id)
        .order_by(TraceRecord.seq_no, TraceRecord.id)
    ).scalars().all()


# ===== plan / lesson =====
def add_plan(db: Session, row: RepairPlan) -> RepairPlan:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_plans(db: Session, task_id: int):
    return db.execute(select(RepairPlan).where(RepairPlan.task_id == task_id).order_by(desc(RepairPlan.id))).scalars().all()


def add_lesson(db: Session, row: Lesson) -> Lesson:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_lessons(db: Session, task_id: int):
    return db.execute(select(Lesson).where(Lesson.task_id == task_id).order_by(desc(Lesson.id))).scalars().all()


# ===== exp helper =====
def delete_exp_owned(db: Session, exp_id: int, user_id: int) -> bool:
    exp = db.execute(select(Experiment).where(Experiment.id == exp_id, Experiment.user_id == user_id)).scalar_one_or_none()
    if not exp:
        return False
    try:
        db.execute(delete(ExperimentItem).where(ExperimentItem.exp_id == exp_id))
        db.delete(exp)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
