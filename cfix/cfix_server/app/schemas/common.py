from pydantic import BaseModel


class Resp(BaseModel):
    code: int = 200
    msg: str = "ok"
    data: dict | list | str | int | None = None
