from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class TestCase(Base):
    __tablename__ = "cf_case"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("cf_task.id", ondelete="CASCADE"), index=True)
    src_type: Mapped[str] = mapped_column(String(16), default="custom")
    case_in: Mapped[str | None] = mapped_column(Text, nullable=True)
    expect_out: Mapped[str | None] = mapped_column(Text, nullable=True)
    assert_text: Mapped[str] = mapped_column(Text, comment="断言表达式")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    sort_no: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
