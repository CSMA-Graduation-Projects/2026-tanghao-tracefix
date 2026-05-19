"""FastAPI 服务入口，负责装配全局中间件、业务路由和启动初始化。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cfg import settings
from app.core.log import get_logger
from app.api.v1 import auth, chat, data, exp, model, run, stream, task, ver
from app.db.base import Base
from app.db.sess import engine

# 创建应用实例，并统一挂载后续中间件与路由。
app = FastAPI(title=settings.app_name, debug=settings.app_debug)
logger = get_logger("startup")

# 统一开放前端访问所需的跨域能力。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 将各业务域接口注册到统一的 API 前缀下。
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
    # 启动时兜底建表，避免本地首次运行因缺表直接失败。
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表初始化完成")
    except Exception:
        logger.exception("数据库表初始化失败，服务继续启动")


@app.get("/")
def root():
    # 根路径仅用于存活探针和快速联通性检查。
    return {"msg": "cfix-server running"}
