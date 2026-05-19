"""通用领域的请求与响应模型定义，约束前后端交互数据结构。"""

from pydantic import BaseModel


class Resp(BaseModel):
    code: int = 200
    msg: str = "ok"
    data: dict | list | str | int | None = None
