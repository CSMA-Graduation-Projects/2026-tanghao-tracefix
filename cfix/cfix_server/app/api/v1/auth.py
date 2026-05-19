"""认证相关的 FastAPI 路由，负责暴露对应业务域接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.core.sec import verify_pwd, create_token, hash_pwd
from app.repo.user_repo import get_user_by_username, create_user
from app.schemas.auth import LoginIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = get_user_by_username(db, payload.username)
    if not user:
        # 第一版为了方便启动演示：若用户不存在则自动注册
        user = create_user(db, payload.username, hash_pwd(payload.password), role="user")
    if not verify_pwd(payload.password, user.pwd_hash):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    token = create_token(user.username)
    return {"code": 200, "msg": "ok", "data": {"access_token": token, "token_type": "bearer"}}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "code": 200,
        "msg": "ok",
        "data": {"id": user.id, "username": user.username, "role": user.role, "status": user.status},
    }


@router.post("/logout")
def logout():
    return {"code": 200, "msg": "ok", "data": True}
