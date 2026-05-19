"""运行记录相关的 FastAPI 路由，负责暴露对应业务域接口。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.repo.task_repo import (
    get_task_owned,
    get_run_owned,
    list_runs_owned,
    list_trace_owned,
    list_case_results,
)

router = APIRouter(prefix="/run", tags=["run"])


@router.get("/task/{task_id}")
def task_runs(task_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = get_task_owned(db, task_id, user.id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")
    rows = list_runs_owned(db, task_id, user.id)
    return {"code": 200, "msg": "ok", "data": [{"id": x.id, "ver_id": x.ver_id, "result": x.result, "round_no": x.round_no, "pass_cnt": x.pass_cnt, "total_cnt": x.total_cnt, "time_ms": x.time_ms} for x in rows]}


@router.get("/{run_id}")
def run_detail(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_run_owned(db, run_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail="运行记录不存在或无权访问")
    return {
        "code": 200,
        "msg": "ok",
        "data": {
            "id": row.id,
            "task_id": row.task_id,
            "ver_id": row.ver_id,
            "round_no": row.round_no,
            "run_type": row.run_type,
            "result": row.result,
            "pass_cnt": row.pass_cnt,
            "total_cnt": row.total_cnt,
            "score": row.score,
            "err_type": row.err_type,
            "err_msg": row.err_msg,
            "tb_text": row.tb_text,
            "trace_sum": row.trace_sum,
            "stdout": row.stdout,
            "stderr": row.stderr,
            "time_ms": row.time_ms,
            "mem_kb": row.mem_kb,
            "line_no": row.line_no,
        },
    }


@router.get("/{run_id}/fb")
def run_feedback(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_run_owned(db, run_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail="运行记录不存在或无权访问")
    data = {
        "run_id": row.id,
        "result": row.result,
        "err_type": row.err_type,
        "err_msg": row.err_msg,
        "line_no": row.line_no,
        "pass_cnt": row.pass_cnt,
        "total_cnt": row.total_cnt,
        "trace_sum": row.trace_sum,
        "time_ms": row.time_ms,
    }
    return {"code": 200, "msg": "ok", "data": data}


@router.get("/{run_id}/trace")
def run_trace(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = list_trace_owned(db, run_id, user.id)
    data = [
        {
            "seq_no": x.seq_no,
            "node_type": x.node_type,
            "func_name": x.func_name,
            "var_name": x.var_name,
            "line_no": x.line_no,
            "log_text": x.log_text,
        }
        for x in rows
    ]
    return {"code": 200, "msg": "ok", "data": data}


@router.get("/{run_id}/cases")
def run_cases(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    row = get_run_owned(db, run_id, user.id)
    if not row:
        raise HTTPException(status_code=404, detail="运行记录不存在或无权访问")
    rows = list_case_results(db, run_id)
    data = [
        {
            "case_id": x.case_id,
            "result": x.result,
            "actual_out": x.actual_out,
            "err_msg": x.err_msg,
            "time_ms": x.time_ms,
        }
        for x in rows
    ]
    return {"code": 200, "msg": "ok", "data": data}
