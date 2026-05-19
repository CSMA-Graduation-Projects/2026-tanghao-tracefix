"""轨迹服务，负责封装对应业务域的核心流程。"""

import json
from sqlalchemy.orm import Session

from app.agent.inst_agent import InstAgent
from app.models.trace import TraceRecord
from app.sand.runner import Runner
from app.sand.trace_wrap import iter_trace_payloads, payload_to_text, summarize_trace


class TraceService:
    """真实 trace 服务：先插桩，再执行插桩代码，再落结构化轨迹。"""

    def __init__(self):
        self.inst_agent = InstAgent()
        self.runner = Runner()

    @staticmethod
    def _map_node_type(event: str) -> str:
        mapping = {
            "enter": "enter",
            "var": "var",
            "branch": "branch",
            "loop": "loop",
            "ret": "ret",
            "error": "exit",
        }
        return mapping.get(event, "var")

    def build_trace_records(
        self,
        run_id: int,
        stdout: str,
        err_type: str | None = None,
        err_msg: str | None = None,
        line_no: int | None = None,
    ) -> tuple[list[TraceRecord], str]:
        items: list[TraceRecord] = []
        seq = 1

        for payload in iter_trace_payloads(stdout):
            event = payload.get("event", "raw")
            items.append(
                TraceRecord(
                    run_id=run_id,
                    seq_no=seq,
                    node_type=self._map_node_type(event),
                    func_name=payload.get("func"),
                    var_name=payload.get("var"),
                    old_val=None,
                    new_val=payload.get("value"),
                    branch_flag=payload.get("branch"),
                    loop_idx=None,
                    line_no=payload.get("line"),
                    log_text=payload_to_text(payload),
                )
            )
            seq += 1

        if err_type:
            items.append(
                TraceRecord(
                    run_id=run_id,
                    seq_no=seq,
                    node_type="exit",
                    func_name=None,
                    var_name=None,
                    old_val=None,
                    new_val=None,
                    branch_flag=None,
                    loop_idx=None,
                    line_no=line_no,
                    log_text=f"异常 {err_type}: {err_msg or ''}",
                )
            )

        return items, summarize_trace(stdout, err_type=err_type, err_msg=err_msg, line_no=line_no)

    def trace_case(
        self,
        db: Session,
        run_id: int,
        code_text: str,
        assert_text: str,
        prelude_text: str = "",
        problem_text: str = "",
        err_text: str = "",
        inst_sugg: str = "",
        scene: str = "func",
    ) -> dict:
        """对指定用例执行真正的插桩链路。

        返回：
        - inst_code: 插桩后的代码
        - exec_result: 插桩代码执行结果
        - trace_items: 结构化轨迹
        - trace_sum: 轨迹摘要
        """
        inst_code = self.inst_agent.run(
            code_text=code_text,
            err_text=err_text,
            inst_sugg=inst_sugg,
            problem_text=problem_text,
            scene=scene,
        )
        merged_case = '\n\n'.join([part for part in [prelude_text.strip(), assert_text.strip()] if part])
        rs = self.runner.run_trace_one(inst_code, merged_case)
        trace_items, trace_sum = self.build_trace_records(
            run_id=run_id,
            stdout=rs.stdout or "",
            err_type=rs.err_type,
            err_msg=rs.err_msg,
            line_no=rs.line_no,
        )
        return {
            "inst_code": inst_code,
            "exec_result": rs,
            "trace_items": trace_items,
            "trace_sum": trace_sum,
        }