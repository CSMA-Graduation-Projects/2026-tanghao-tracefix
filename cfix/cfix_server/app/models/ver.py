"""代码版本领域的 ORM 模型定义，用于映射数据库表结构。"""

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class CodeVersion(Base):
    __tablename__ = "cf_ver"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("cf_task.id", ondelete="CASCADE"), index=True)
    ver_no: Mapped[int] = mapped_column(Integer, default=1)
    ver_type: Mapped[str] = mapped_column(String(16), default="init")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("cf_ver.id", ondelete="SET NULL"), nullable=True)
    code_text: Mapped[str] = mapped_column(Text)
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
