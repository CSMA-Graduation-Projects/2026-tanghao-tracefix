from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.schemas.exp import ExpCreate
from app.svc.exp_svc import ExpService
from app.data.exp_profile_store import delete_profile_for_exp
from app.repo.task_repo import delete_exp_owned

router = APIRouter(prefix="/exp", tags=["exp"])
svc = ExpService()


def _pack_row(db: Session, user_id: int, row):
    progress = svc.progress(db, user_id, row.id)
    report = svc.report(db, user_id, row.id)
    profile = svc.get_profile_info(exp_id=row.id)
    return {
        "id": row.id,
        "name": row.name,
        "dataset": row.dataset,
        "model_id": row.model_id,
        "sample_cnt": row.sample_cnt,
        "max_round": row.max_round,
        "status": row.status,
        "progress": progress["progress"],
        "progress_text": progress["progress_text"],
        "phase": progress.get("phase"),
        "current_problem_no": progress.get("current_problem_no"),
        "current_problem_title": progress.get("current_problem_title"),
        "current_index": progress.get("current_index"),
        "current_task_id": progress.get("current_task_id"),
        "total": progress.get("total"),
        "logs": progress.get("logs") or [],
        "report": report,
        "report_source": "server",
        "profile": profile,
    }



@router.get("/profiles")
def list_exp_profiles():
    return {"code": 200, "msg": "ok", "data": svc.list_profiles()}


@router.get("/compare")
def compare_exp(exp_ids: str = Query(..., description="逗号分隔的 2~3 个实验ID"), db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        ids = [int(x) for x in str(exp_ids or '').split(',') if str(x).strip()]
        data = svc.compare(db, user.id, ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 200, "msg": "ok", "data": data}


@router.get("")
def list_exp(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = svc.list_exp(db, user.id)
    return {"code": 200, "msg": "ok", "data": [_pack_row(db, user.id, x) for x in rows]}


@router.post("")
def create_exp(payload: ExpCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = svc.create_exp(db, user.id, payload)
    return {"code": 200, "msg": "ok", "data": {"id": row.id, "status": row.status}}




@router.delete("/{exp_id}")
def delete_exp(exp_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ok = delete_exp_owned(db, exp_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="实验不存在或无权访问")
    delete_profile_for_exp(exp_id)
    return {"code": 200, "msg": "ok", "data": True}


@router.get("/{exp_id}")
def get_exp_detail(exp_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = svc.get_exp(db, user.id, exp_id)
    if not row:
        raise HTTPException(status_code=404, detail="实验不存在或无权访问")
    return {"code": 200, "msg": "ok", "data": _pack_row(db, user.id, row)}


@router.post("/{exp_id}/start")
def start_exp(exp_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        row = svc.start_exp(db, user.id, exp_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    started = svc.launch_exp_job(row.id)
    progress = svc.progress(db, user.id, row.id)
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "id": row.id,
            "status": row.status,
            "progress": progress["progress"],
            "progress_text": progress["progress_text"],
            "phase": progress.get("phase"),
            "current_problem_no": progress.get("current_problem_no"),
            "current_problem_title": progress.get("current_problem_title"),
            "current_index": progress.get("current_index"),
            "current_task_id": progress.get("current_task_id"),
            "total": progress.get("total"),
            "logs": progress.get("logs") or [],
            "started": started,
        },
    }


@router.post("/{exp_id}/stop")
def stop_exp(exp_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        row = svc.stop_exp(db, user.id, exp_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    progress = svc.progress(db, user.id, row.id)
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "id": row.id,
            "status": row.status,
            "progress": progress["progress"],
            "progress_text": progress["progress_text"],
            "phase": progress.get("phase"),
            "current_problem_no": progress.get("current_problem_no"),
            "current_problem_title": progress.get("current_problem_title"),
            "current_index": progress.get("current_index"),
            "current_task_id": progress.get("current_task_id"),
            "total": progress.get("total"),
            "logs": progress.get("logs") or [],
        },
    }


@router.get("/{exp_id}/item")
def get_exp_items(exp_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        data = svc.items(db, user.id, exp_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "msg": "ok", "data": data}


@router.get("/{exp_id}/report")
def get_exp_report(exp_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        data = svc.report(db, user.id, exp_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "msg": "ok", "data": data}


@router.get("/{exp_id}/chart")
def get_exp_chart(exp_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        data = svc.chart(db, user.id, exp_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"code": 200, "msg": "ok", "data": data}
