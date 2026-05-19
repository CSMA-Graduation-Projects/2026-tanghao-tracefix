"""任务领域的 ORM 模型定义，用于映射数据库表结构。"""

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class Task(Base):
    __tablename__ = "cf_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("cf_user.id", ondelete="CASCADE"), index=True)
    sess_id: Mapped[int | None] = mapped_column(ForeignKey("cf_chat_sess.id", ondelete="SET NULL"), nullable=True, index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("cf_model.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    lang: Mapped[str] = mapped_column(String(16), default="python")
    scene: Mapped[str] = mapped_column(String(16), default="func")
    dataset: Mapped[str] = mapped_column(String(32), default="custom")
    problem_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    max_round: Mapped[int] = mapped_column(Integer, default=3)
    cur_round: Mapped[int] = mapped_column(Integer, default=0)
    best_ver_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    best_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_trace_on: Mapped[bool] = mapped_column(Boolean, default=True)
    is_lesson_on: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
