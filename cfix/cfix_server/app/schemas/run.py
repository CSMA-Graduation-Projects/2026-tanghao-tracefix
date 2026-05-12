from pydantic import BaseModel


class RunFbOut(BaseModel):
    run_id: int
    result: str
    err_type: str | None = None
    err_msg: str | None = None
    line_no: int | None = None
    pass_cnt: int
    total_cnt: int
    trace_sum: str | None = None
    time_ms: int
