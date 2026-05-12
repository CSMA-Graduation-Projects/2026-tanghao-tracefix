from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class TraceRecord(Base):
    __tablename__ = "cf_trace"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("cf_run.id", ondelete="CASCADE"), index=True)
    seq_no: Mapped[int] = mapped_column(Integer, default=1)
    node_type: Mapped[str] = mapped_column(String(16), comment="enter/exit/var/branch/loop/ret")
    func_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    var_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    old_val: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_val: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_flag: Mapped[str | None] = mapped_column(String(16), nullable=True)
    loop_idx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    log_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
