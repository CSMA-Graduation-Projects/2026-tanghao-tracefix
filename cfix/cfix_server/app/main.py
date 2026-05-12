from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cfg import settings
from app.api.v1 import auth, chat, data, exp, model, run, stream, task, ver

app = FastAPI(title=settings.app_name, debug=settings.app_debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
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


@app.get("/")
def root():
    return {"msg": "cfix-server running"}
