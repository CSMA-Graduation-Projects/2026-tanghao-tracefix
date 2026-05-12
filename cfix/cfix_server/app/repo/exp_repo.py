from sqlalchemy import select, desc, delete
from sqlalchemy.orm import Session
from app.models.exp import Experiment, ExperimentItem


def list_exps(db: Session, user_id: int):
    return db.execute(select(Experiment).where(Experiment.user_id == user_id).order_by(desc(Experiment.id))).scalars().all()


def get_exp(db: Session, exp_id: int) -> Experiment | None:
    return db.get(Experiment, exp_id)


def get_exp_owned(db: Session, exp_id: int, user_id: int) -> Experiment | None:
    return db.execute(
        select(Experiment).where(Experiment.id == exp_id, Experiment.user_id == user_id)
    ).scalar_one_or_none()


def create_exp(db: Session, exp: Experiment) -> Experiment:
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def save_exp(db: Session, exp: Experiment) -> Experiment:
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def clear_exp_items(db: Session, exp_id: int):
    db.execute(delete(ExperimentItem).where(ExperimentItem.exp_id == exp_id))
    db.commit()


def add_exp_item(db: Session, item: ExperimentItem) -> ExperimentItem:
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_exp_items(db: Session, exp_id: int):
    return db.execute(
        select(ExperimentItem).where(ExperimentItem.exp_id == exp_id).order_by(ExperimentItem.problem_no, ExperimentItem.id)
    ).scalars().all()
