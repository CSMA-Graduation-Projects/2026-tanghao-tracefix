"""经验总结领域的 ORM 模型定义，用于映射数据库表结构。"""

from sqlalchemy import BigInteger, ForeignKey, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class Lesson(Base):
    __tablename__ = "cf_lesson"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("cf_task.id", ondelete="CASCADE"), index=True)
    round_no: Mapped[int] = mapped_column(Integer, default=1)
    bad_pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_run_id: Mapped[int | None] = mapped_column(ForeignKey("cf_run.id", ondelete="SET NULL"), nullable=True)
    from_plan_id: Mapped[int | None] = mapped_column(ForeignKey("cf_plan.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
