from pydantic import BaseModel


class TraceOut(BaseModel):
    seq_no: int
    node_type: str
    func_name: str | None = None
    var_name: str | None = None
    line_no: int | None = None
    log_text: str | None = None
