"""用户领域的 ORM 模型定义，用于映射数据库表结构。"""

from datetime import datetime
from sqlalchemy import BigInteger, String, SmallInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class User(Base):
    __tablename__ = "cf_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="用户名")
    pwd_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希")
    role: Mapped[str] = mapped_column(String(16), default="user", comment="角色")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="状态：1启用 0停用")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
