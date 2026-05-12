from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from datetime import datetime


class ModelCfg(Base):
    __tablename__ = "cf_model"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uk_cf_model_user_provider"),
        Index("idx_cf_model_active", "user_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("cf_user.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64), comment="显示名称")
    provider: Mapped[str] = mapped_column(String(32), index=True, comment="提供方")
    model_key: Mapped[str] = mapped_column(String(128), comment="模型标识")
    base_url: Mapped[str] = mapped_column(String(255), default="", comment="接口基础URL")
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True, comment="加密后的API KEY")
    temp: Mapped[int] = mapped_column(Integer, default=20, comment="温度*100")
    max_tok: Mapped[int] = mapped_column(Integer, default=4096)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
