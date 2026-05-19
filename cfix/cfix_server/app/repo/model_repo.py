"""模型配置数据访问层，负责组织对应实体的数据库读写。"""

from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from app.models.model_cfg import ModelCfg


def list_user_model_cfgs(db: Session, user_id: int) -> list[ModelCfg]:
    return db.execute(
        select(ModelCfg)
        .where(ModelCfg.user_id == user_id)
        .order_by(desc(ModelCfg.is_active), ModelCfg.provider.asc(), desc(ModelCfg.id))
    ).scalars().all()


def get_user_model_cfg_by_provider(db: Session, user_id: int, provider: str) -> ModelCfg | None:
    return db.execute(
        select(ModelCfg)
        .where(ModelCfg.user_id == user_id, ModelCfg.provider == provider)
        .order_by(desc(ModelCfg.id))
    ).scalar_one_or_none()


def get_model_cfg_by_id(db: Session, model_id: int) -> ModelCfg | None:
    return db.get(ModelCfg, model_id)


def get_active_model_cfg(db: Session, user_id: int) -> ModelCfg | None:
    return db.execute(
        select(ModelCfg)
        .where(ModelCfg.user_id == user_id, ModelCfg.is_active.is_(True))
        .order_by(desc(ModelCfg.id))
    ).scalar_one_or_none()


def save_model_cfg(db: Session, row: ModelCfg) -> ModelCfg:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def deactivate_user_model_cfgs(db: Session, user_id: int, *, exclude_id: int | None = None):
    stmt = update(ModelCfg).where(ModelCfg.user_id == user_id)
    if exclude_id is not None:
        stmt = stmt.where(ModelCfg.id != exclude_id)
    db.execute(stmt.values(is_active=False))
    db.commit()