"""模型配置相关的 FastAPI 路由，负责暴露对应业务域接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.schemas.model_cfg import ModelCfgSaveIn
from app.svc.model_svc import ModelService

router = APIRouter(prefix="/model", tags=["model"])
svc = ModelService()


@router.get("/config")
def get_model_config_api(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"code": 200, "msg": "ok", "data": svc.get_user_settings(db, user.id)}


@router.put("/config")
def save_model_config_api(payload: ModelCfgSaveIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        data = svc.save_user_config(db, user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": 200, "msg": "ok", "data": data}