from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.schemas.chat import ChatSessCreate, ChatSessUpdate, ChatMsgCreate, ChatToTaskIn
from app.svc.chat_svc import ChatService
from app.repo.task_repo import get_chat_sess_owned, update_chat_sess_title

router = APIRouter(prefix="/chat", tags=["chat"])
svc = ChatService()


@router.get("/sess")
def list_sess(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = svc.list_sess(db, user.id)
    return {"code": 200, "msg": "ok", "data": [{"id": x.id, "title": x.title} for x in rows]}


@router.post("/sess")
def create_sess(payload: ChatSessCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = svc.create_sess(db, user.id, payload.title)
    return {"code": 200, "msg": "ok", "data": {"id": row.id, "title": row.title}}


@router.get("/sess/{sess_id}")
def get_sess(sess_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_chat_sess_owned(db, sess_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return {"code": 200, "msg": "ok", "data": {"id": row.id, "title": row.title, "last_msg": row.last_msg}}




@router.put("/sess/{sess_id}")
def update_sess(sess_id: int, payload: ChatSessUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_chat_sess_owned(db, sess_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    row = update_chat_sess_title(db, row, payload.title.strip())
    return {"code": 200, "msg": "ok", "data": {"id": row.id, "title": row.title}}


@router.get("/sess/{sess_id}/msg")
def list_msg(sess_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sess = get_chat_sess_owned(db, sess_id, user.id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    rows = svc.get_msgs(db, sess_id)
    return {"code": 200, "msg": "ok", "data": [{"id": x.id, "role": x.role, "content": x.content} for x in rows]}


@router.post("/sess/{sess_id}/msg")
def add_msg(sess_id: int, payload: ChatMsgCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sess = get_chat_sess_owned(db, sess_id, user.id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    row = svc.add_msg(db, sess_id, payload.role, payload.msg_type, payload.content)
    return {"code": 200, "msg": "ok", "data": {"id": row.id}}


@router.post("/sess/{sess_id}/to-task")
def to_task(sess_id: int, payload: ChatToTaskIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sess = get_chat_sess_owned(db, sess_id, user.id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    task = svc.to_task(db, user.id, sess_id, payload)
    return {"code": 200, "msg": "ok", "data": {"task_id": task.id, "status": task.status}}
