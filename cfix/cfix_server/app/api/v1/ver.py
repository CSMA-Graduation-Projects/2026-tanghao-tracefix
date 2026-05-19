"""版本相关的 FastAPI 路由，负责暴露对应业务域接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.llm.base import LLMBase
from app.repo.task_repo import get_ver_owned, get_latest_version, list_versions
from app.svc.rb_svc import RollbackService
from app.utils.diff import make_diff

router = APIRouter(prefix="/ver", tags=["ver"])
rb_svc = RollbackService()


@router.get("/{ver_id}")
def ver_detail(ver_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_ver_owned(db, ver_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail="版本不存在或无权访问")
    return {"code": 200, "msg": "ok", "data": {"id": row.id, "ver_no": row.ver_no, "ver_type": row.ver_type, "note": row.note}}


@router.get("/{ver_id}/code")
def ver_code(ver_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_ver_owned(db, ver_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail="版本不存在或无权访问")
    code_text = LLMBase.sanitize_generated_code(row.code_text or "") or (row.code_text or "")
    return {"code": 200, "msg": "ok", "data": {"id": row.id, "code_text": code_text}}


@router.get("/{ver_id}/diff/{to_id}")
def ver_diff(ver_id: int, to_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = get_ver_owned(db, ver_id, user.id)
    b = get_ver_owned(db, to_id, user.id)
    if not a or not b:
        raise HTTPException(status_code=404, detail="版本不存在或无权访问")
    if a.task_id != b.task_id:
        raise HTTPException(status_code=400, detail="只能比较同一任务下的版本")
    code_a = LLMBase.sanitize_generated_code(a.code_text or "") or (a.code_text or "")
    code_b = LLMBase.sanitize_generated_code(b.code_text or "") or (b.code_text or "")
    return {"code": 200, "msg": "ok", "data": {"diff": make_diff(code_a, code_b)}}


@router.post("/{ver_id}/rollback")
def ver_manual_rollback(ver_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """手动把指定历史版本落成一个新的 rollback 基线版本。"""
    target = get_ver_owned(db, ver_id, user.id)
    if not target:
        raise HTTPException(status_code=404, detail="版本不存在或无权访问")

    latest = get_latest_version(db, target.task_id)
    if not latest:
        raise HTTPException(status_code=404, detail="当前任务没有可回退的最新版本")

    if latest.id == target.id:
        raise HTTPException(status_code=400, detail="当前最新版本就是目标版本，无需重复回退")

    rollback_ver = rb_svc.make_rollback_version(
        db=db,
        task_id=target.task_id,
        rollback_to=target,
        from_ver_id=latest.id,
        next_ver_no=len(list_versions(db, target.task_id)) + 1,
        note=f"手动回退：从最新版本 v{latest.ver_no} 切回 v{target.ver_no}",
    )
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "task_id": target.task_id,
            "ver_id": rollback_ver.id,
            "ver_no": rollback_ver.ver_no,
            "ver_type": rollback_ver.ver_type,
        },
    }
