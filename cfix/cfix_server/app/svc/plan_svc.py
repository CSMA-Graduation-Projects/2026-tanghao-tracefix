from sqlalchemy.orm import Session

from app.agent.ana_agent import AnaAgent
from app.models.plan import RepairPlan
from app.repo.task_repo import add_plan, get_task, list_cases, list_lessons
from app.svc.model_svc import resolve_llm_client
from app.utils.fail_focus import build_file_fix_guard, summarize_lesson_history


class PlanService:
    def build_plan(
        self,
        db: Session,
        task_id: int,
        run_id: int,
        round_no: int,
        problem_text: str,
        code_text: str,
        err_text: str,
        trace_sum: str,
        lesson_on: bool = True,
        scene: str = "func",
        title: str = '',
    ):
        task = get_task(db, task_id)
        agent = AnaAgent(client=resolve_llm_client(db, user_id=task.user_id if task else None, model_id=task.model_id if task else None))
        # lesson_on=false 时，不读取历史 lesson，也不把旧失败经验混入本轮分析。
        lesson_text = ""
        if lesson_on:
            lessons = list_lessons(db, task_id)
            lesson_text = "\n".join([x.lesson_text or "" for x in lessons[:3]])
            lesson_text = summarize_lesson_history(lesson_text, scene=scene)
        if (scene or 'func') == 'file':
            guard = build_file_fix_guard(err_text, lesson_text)
            if guard:
                lesson_text = (lesson_text + "\n\n[FILE_FIX_GUARD]\n" + guard).strip()

        case_texts = [str(x.assert_text or '').strip() for x in list_cases(db, task_id) if str(x.assert_text or '').strip()]

        rs = agent.run(
            problem_text=problem_text,
            code_text=code_text,
            err_text=err_text,
            trace_sum=trace_sum,
            lesson_text=lesson_text,
            scene=scene,
            title=title,
            case_texts=case_texts,
        )

        prompt_parts = [
            f"ERR:\n{err_text}",
            f"TRACE:\n{trace_sum or '[trace disabled or empty]'}",
        ]
        if lesson_on:
            prompt_parts.append(f"LESSON:\n{lesson_text or '[no lessons]'}")
        else:
            prompt_parts.append("LESSON:\n[disabled]")

        plan = RepairPlan(
            task_id=task_id,
            run_id=run_id,
            round_no=round_no,
            root_cause=rs["root_cause"],
            fix_plan=rs["fix_plan"],
            inst_sugg=rs["inst_sugg"],
            prompt_text="\n\n".join(prompt_parts),
        )
        return add_plan(db, plan)
