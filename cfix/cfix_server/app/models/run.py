from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class RunRecord(Base):
    __tablename__ = "cf_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("cf_task.id", ondelete="CASCADE"), index=True)
    ver_id: Mapped[int] = mapped_column(ForeignKey("cf_ver.id", ondelete="CASCADE"), index=True)
    round_no: Mapped[int] = mapped_column(Integer, default=0)
    run_type: Mapped[str] = mapped_column(String(16), default="test")
    result: Mapped[str] = mapped_column(String(16), default="fail")
    pass_cnt: Mapped[int] = mapped_column(Integer, default=0)
    total_cnt: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    err_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    err_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    tb_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_sum: Mapped[str | None] = mapped_column(Text, nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_ms: Mapped[int] = mapped_column(Integer, default=0)
    mem_kb: Mapped[int] = mapped_column(Integer, default=0)
    line_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class CaseResult(Base):
    __tablename__ = "cf_case_res"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("cf_run.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cf_case.id", ondelete="CASCADE"), index=True)
    result: Mapped[str] = mapped_column(String(16), default="fail")
    actual_out: Mapped[str | None] = mapped_column(Text, nullable=True)
    err_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
