"""安全与鉴权模块，负责提供后端运行所需的基础能力。"""

from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.cfg import settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_pwd(raw_pwd: str) -> str:
    return pwd_ctx.hash(raw_pwd)


def verify_pwd(raw_pwd: str, pwd_hash: str) -> bool:
    return pwd_ctx.verify(raw_pwd, pwd_hash)


def create_token(sub: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_min)
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def parse_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except JWTError:
        return None
