"""任务相关的 FastAPI 路由，负责暴露对应业务域接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.case import TestCase
from app.repo.task_repo import (
    get_task_owned,
    list_tasks_owned,
    list_versions,
    list_cases,
    list_plans,
    list_lessons,
    delete_task_owned,
    stop_task_owned,
)
from app.schemas.task import AutoFixIn, CaseGenIn, GenTaskIn, RunTaskIn, TaskCaseReplaceIn, TaskCreate, TaskUpdateIn
from app.svc.case_svc import CaseService
from app.svc.task_svc import TaskService
from app.utils.case_block import normalize_case_rows

router = APIRouter(prefix='/task', tags=['task'])
svc = TaskService()
case_svc = CaseService()


def _infer_case_mode(scene: str, rows: list[TestCase]) -> str:
    if scene not in {'file', 'class'}:
        return 'line'
    srcs = {str(getattr(x, 'src_type', '') or '').strip().lower() for x in (rows or [])}
    if any(src == 'setup' or 'block' in src for src in srcs):
        return 'block'
    return 'legacy_line'


def _legacy_case_warning(scene: str, rows: list[TestCase]) -> str | None:
    mode = _infer_case_mode(scene, rows)
    if mode != 'legacy_line':
        return None
    return '当前任务仍在使用旧版逐行测试用例（legacy_line），file/class 场景下会把多行测试块拆坏，建议复制题目与测试块后重新创建一个新任务。'


@router.get('')
def list_task_api(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = list_tasks_owned(db, user.id)
    data = [
        {
            'id': x.id,
            'title': x.title,
            'status': x.status,
            'cur_round': x.cur_round,
            'best_ver_id': x.best_ver_id,
            'best_score': x.best_score,
            'dataset': x.dataset,
            'scene': x.scene,
        }
        for x in rows
    ]
    return {'code': 200, 'msg': 'ok', 'data': data}


@router.post('')
def create_task_api(payload: TaskCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = svc.create_new_task(db, user.id, payload)
    return {'code': 200, 'msg': 'ok', 'data': {'id': row.id, 'status': row.status}}


@router.put('/{task_id}')
def update_task_api(task_id: int, payload: TaskUpdateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_task_owned(db, task_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    try:
        row = svc.update_task_meta(db, task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        'code': 200,
        'msg': 'ok',
        'data': {
            'id': row.id,
            'sess_id': row.sess_id,
            'title': row.title,
            'problem_text': row.problem_text,
            'dataset': row.dataset,
            'lang': row.lang,
            'scene': row.scene,
            'max_round': row.max_round,
            'is_trace_on': bool(row.is_trace_on),
            'is_lesson_on': bool(row.is_lesson_on),
        },
    }


@router.get('/{task_id}')
def task_detail_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_task_owned(db, task_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    case_rows = list_cases(db, task_id)
    case_mode = _infer_case_mode(row.scene, case_rows)
    return {
        'code': 200,
        'msg': 'ok',
        'data': {
            'id': row.id,
            'sess_id': row.sess_id,
            'title': row.title,
            'problem_text': row.problem_text,
            'status': row.status,
            'cur_round': row.cur_round,
            'best_ver_id': row.best_ver_id,
            'best_score': row.best_score,
            'dataset': row.dataset,
            'scene': row.scene,
            'lang': row.lang,
            'max_round': row.max_round,
            'is_trace_on': bool(row.is_trace_on),
            'is_lesson_on': bool(row.is_lesson_on),
            'case_mode': case_mode,
            'legacy_case_warning': _legacy_case_warning(row.scene, case_rows),
            'can_rerun': bool(list_versions(db, task_id)),
        },
    }


@router.delete('/{task_id}')
def delete_task_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        ok = delete_task_owned(db, task_id, user.id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail=f'删除任务失败：{exc}') from exc
    if not ok:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    return {'code': 200, 'msg': 'ok', 'data': True}


@router.post('/{task_id}/gen')
def gen_task_api(task_id: int, payload: GenTaskIn | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    payload = payload or GenTaskIn()
    rs = svc.gen_init(
        db,
        task_id,
        auto_gen_cases=bool(payload.auto_gen_cases),
        case_cfg=payload.case_cfg.model_dump() if hasattr(payload.case_cfg, 'model_dump') else dict(payload.case_cfg),
    )
    return {
        'code': 200,
        'msg': 'ok',
        'data': {
            'ver_id': rs.ver.id,
            'case_count': len(rs.generated_cases),
            'generated_cases': rs.generated_cases,
            'case_source': rs.case_source,
            'gen_source': rs.gen_source,
        },
    }


@router.put('/{task_id}/case')
def replace_task_cases_api(task_id: int, payload: TaskCaseReplaceIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    rows = svc.replace_task_cases(db, task_id, payload.cases)
    return {'code': 200, 'msg': 'ok', 'data': {'case_count': len(rows)}}


@router.post('/{task_id}/run')
def run_task_api(task_id: int, payload: RunTaskIn | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    try:
        if payload is not None and payload.cases is not None:
            svc.replace_task_cases(db, task_id, payload.cases)
        row = svc.run_latest(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'code': 200, 'msg': 'ok', 'data': {'run_id': row.id, 'result': row.result}}


@router.post('/{task_id}/stop')
def stop_task_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = stop_task_owned(db, task_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    return {'code': 200, 'msg': 'ok', 'data': {'id': row.id, 'status': row.status}}


@router.post('/{task_id}/auto')
def auto_task_api(task_id: int, payload: AutoFixIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    try:
        if payload.cases is not None:
            svc.replace_task_cases(db, task_id, payload.cases)
        data = svc.auto_fix(
            db=db,
            task_id=task_id,
            max_round=payload.max_round,
            trace_on=payload.trace_on,
            lesson_on=payload.lesson_on,
            stop_on_pass=payload.stop_on_pass,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f'自动修复失败：{exc}') from exc
    return {'code': 200, 'msg': 'ok', 'data': data}


@router.get('/{task_id}/status')
def task_status_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_task_owned(db, task_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    return {'code': 200, 'msg': 'ok', 'data': {'id': row.id, 'status': row.status, 'cur_round': row.cur_round, 'best_ver_id': row.best_ver_id, 'best_score': row.best_score}}


@router.get('/{task_id}/summary')
def task_summary_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_task_owned(db, task_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    vers = list_versions(db, task_id)
    return {'code': 200, 'msg': 'ok', 'data': {'ver_cnt': len(vers), 'best_score': row.best_score, 'best_ver_id': row.best_ver_id}}


@router.get('/{task_id}/ver')
def task_versions_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    rows = list_versions(db, task_id)
    data = [
        {
            'id': x.id,
            'task_id': x.task_id,
            'ver_no': x.ver_no,
            'ver_type': x.ver_type,
            'parent_id': x.parent_id,
            'note': x.note,
        }
        for x in rows
    ]
    return {'code': 200, 'msg': 'ok', 'data': data}


@router.get('/{task_id}/case')
def task_cases_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    rows = normalize_case_rows(task.scene, list_cases(db, task_id))
    data = [
        {'id': x.id, 'sort_no': x.sort_no, 'assert_text': x.assert_text, 'weight': x.weight, 'src_type': x.src_type}
        for x in rows
    ]
    return {'code': 200, 'msg': 'ok', 'data': data}


@router.get('/{task_id}/plan')
def task_plans_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    rows = list_plans(db, task_id)
    data = [
        {'id': x.id, 'round_no': x.round_no, 'root_cause': x.root_cause, 'fix_plan': x.fix_plan, 'inst_sugg': x.inst_sugg}
        for x in rows
    ]
    return {'code': 200, 'msg': 'ok', 'data': data}


@router.get('/{task_id}/lesson')
def task_lessons_api(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在或无权访问')
    rows = list_lessons(db, task_id)
    data = [
        {'id': x.id, 'round_no': x.round_no, 'bad_pattern': x.bad_pattern, 'lesson_text': x.lesson_text}
        for x in rows
    ]
    return {'code': 200, 'msg': 'ok', 'data': data}


# 兼容旧前端或调试调用：仍保留接口，但新交互已经不再依赖独立按钮。
@router.post('/case/gen')
def task_case_gen_api(payload: CaseGenIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cfg = {
        'count': payload.count,
        'preset': payload.preset,
        'focus': payload.focus,
        'hint': payload.hint,
    }
    rows = case_svc.generate_cases(
        problem_text=payload.problem_text,
        scene=payload.scene,
        title=payload.title,
        count=payload.count,
        case_cfg=cfg,
        db=db,
        user_id=user.id,
    )
    data = [
        {
            'src_type': item.src_type,
            'case_in': None,
            'expect_out': None,
            'assert_text': item.assert_text,
            'weight': item.weight,
            'sort_no': item.sort_no,
            'cfg': cfg,
        }
        for item in rows
    ]
    return {'code': 200, 'msg': 'ok', 'data': data}
