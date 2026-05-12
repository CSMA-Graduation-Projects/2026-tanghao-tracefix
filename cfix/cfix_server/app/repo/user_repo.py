from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import User


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def create_user(db: Session, username: str, pwd_hash: str, role: str = "user") -> User:
    user = User(username=username, pwd_hash=pwd_hash, role=role, status=1)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
