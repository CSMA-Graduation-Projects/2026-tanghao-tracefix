"""轨迹领域的请求与响应模型定义，约束前后端交互数据结构。"""

from pydantic import BaseModel


class TraceOut(BaseModel):
    seq_no: int
    node_type: str
    func_name: str | None = None
    var_name: str | None = None
    line_no: int | None = None
    log_text: str | None = None
