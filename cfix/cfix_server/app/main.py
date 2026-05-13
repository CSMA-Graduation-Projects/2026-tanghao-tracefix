from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cfg import settings
from app.core.log import get_logger
from app.api.v1 import auth, chat, data, exp, model, run, stream, task, ver
from app.db.base import Base
from app.db.sess import engine

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
logger = get_logger("startup")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_v1_str)
app.include_router(model.router, prefix=settings.api_v1_str)
app.include_router(chat.router, prefix=settings.api_v1_str)
app.include_router(task.router, prefix=settings.api_v1_str)
app.include_router(run.router, prefix=settings.api_v1_str)
app.include_router(ver.router, prefix=settings.api_v1_str)
app.include_router(exp.router, prefix=settings.api_v1_str)
app.include_router(data.router, prefix=settings.api_v1_str)
app.include_router(stream.router, prefix=settings.api_v1_str)


@app.on_event("startup")
def init_db_on_startup():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表初始化完成")
    except Exception:
        logger.exception("数据库表初始化失败，服务继续启动")


@app.get("/")
def root():
    return {"msg": "cfix-server running"}
