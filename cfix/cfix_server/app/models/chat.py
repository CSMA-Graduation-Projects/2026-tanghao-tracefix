from sqlalchemy import BigInteger, ForeignKey, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class ChatSession(Base):
    __tablename__ = "cf_chat_sess"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("cf_user.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(128), default="新会话")
    last_msg: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class ChatMessage(Base):
    __tablename__ = "cf_chat_msg"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sess_id: Mapped[int] = mapped_column(ForeignKey("cf_chat_sess.id", ondelete="SET NULL"), index=True)
    role: Mapped[str] = mapped_column(String(16), comment="user/assistant/system")
    msg_type: Mapped[str] = mapped_column(String(16), default="text", comment="消息类型")
    content: Mapped[str] = mapped_column(Text, comment="消息正文")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
