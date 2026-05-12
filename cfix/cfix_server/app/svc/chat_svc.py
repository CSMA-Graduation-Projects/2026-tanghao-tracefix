from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.models.chat import ChatSession, ChatMessage
from app.models.task import Task
from app.repo.task_repo import create_task
from app.svc.model_svc import resolve_default_model_id


class ChatService:
    def list_sess(self, db: Session, user_id: int):
        return db.execute(
            select(ChatSession).where(ChatSession.user_id == user_id).order_by(desc(ChatSession.id))
        ).scalars().all()

    def create_sess(self, db: Session, user_id: int, title: str):
        sess = ChatSession(user_id=user_id, title=title)
        db.add(sess)
        db.commit()
        db.refresh(sess)
        return sess

    def get_msgs(self, db: Session, sess_id: int):
        return db.execute(
            select(ChatMessage).where(ChatMessage.sess_id == sess_id).order_by(ChatMessage.id)
        ).scalars().all()

    def add_msg(self, db: Session, sess_id: int, role: str, msg_type: str, content: str):
        msg = ChatMessage(sess_id=sess_id, role=role, msg_type=msg_type, content=content)
        db.add(msg)
        sess = db.get(ChatSession, sess_id)
        if sess:
            sess.last_msg = content[:120]
        db.commit()
        db.refresh(msg)
        return msg

    def to_task(self, db: Session, user_id: int, sess_id: int, payload):
        model_id = payload.model_id if getattr(payload, 'model_id', None) is not None else resolve_default_model_id(db, user_id)
        task = Task(
            user_id=user_id,
            sess_id=sess_id,
            model_id=model_id,
            title=payload.title,
            lang=payload.lang,
            scene=payload.scene,
            dataset=payload.dataset,
            problem_text=payload.problem_text,
            max_round=3,
            is_trace_on=True,
            is_lesson_on=True,
        )
        return create_task(db, task)
