from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class Experiment(Base):
    __tablename__ = "cf_exp"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("cf_user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    dataset: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[int | None] = mapped_column(ForeignKey("cf_model.id", ondelete="SET NULL"), nullable=True)
    sample_cnt: Mapped[int] = mapped_column(Integer, default=0)
    max_round: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class ExperimentItem(Base):
    __tablename__ = "cf_exp_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exp_id: Mapped[int] = mapped_column(ForeignKey("cf_exp.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("cf_task.id", ondelete="CASCADE"), index=True)
    problem_no: Mapped[int] = mapped_column(Integer, default=0)
    init_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    final_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    repair_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    round_used: Mapped[int] = mapped_column(Integer, default=0)
    time_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
