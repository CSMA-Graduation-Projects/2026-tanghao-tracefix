from sqlalchemy import BigInteger, ForeignKey, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class RepairPlan(Base):
    __tablename__ = "cf_plan"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("cf_task.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("cf_run.id", ondelete="CASCADE"), index=True)
    round_no: Mapped[int] = mapped_column(Integer, default=1)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    inst_sugg: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
