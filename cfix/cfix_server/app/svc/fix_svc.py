from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.orm import Session

from app.llm.base import LLMBase
from app.agent.fix_agent import FixAgent
from app.models.ver import CodeVersion
from app.repo.task_repo import add_version, get_task, list_cases, list_lessons
from app.svc.model_svc import resolve_llm_client
from app.utils.fail_focus import build_file_fix_guard, build_focus_guidance_from_err, summarize_lesson_history


@dataclass
class FixVersionResult:
    ver: CodeVersion
    repair_source: str = ""
    repair_error: str = ""
    degraded: bool = False


class FixService:
    def create_fix_version(
        self,
        db: Session,
        task_id: int,
        parent_ver_id: int,
        next_ver_no: int,
        problem_text: str,
        code_text: str,
        fix_plan: str,
        err_text: str = "",
        trace_sum: str = "",
        scene: str = "func",
        lesson_on: bool = True,
        title: str = '',
    ):
        task = get_task(db, task_id)
        agent = FixAgent(client=resolve_llm_client(db, user_id=task.user_id if task else None, model_id=task.model_id if task else None))
        lesson_text = ""
        if lesson_on:
            lessons = list_lessons(db, task_id)
            lesson_text = "\n".join([x.lesson_text or "" for x in lessons[:3]])
            lesson_text = summarize_lesson_history(lesson_text, scene=scene)
        case_texts = [str(x.assert_text or '').strip() for x in list_cases(db, task_id) if str(x.assert_text or '').strip()]
        guard = build_focus_guidance_from_err(err_text, scene=scene, lesson_text=lesson_text)
        guard_text = build_file_fix_guard(err_text, lesson_text) if scene == 'file' else ''
        enriched_plan = fix_plan or ""
        if guard and scene == 'file':
            enriched_plan = (enriched_plan + "\n\n[系统纠偏建议]\n" + guard['fix_plan']).strip()
        if guard_text and scene == 'file':
            enriched_plan = (enriched_plan + "\n\n[稳定失败与保护区域提示]\n" + guard_text).strip()

        repair_error = ''
        degraded = False
        try:
            new_code = agent.run(
                problem_text=problem_text,
                code_text=code_text,
                fix_plan=enriched_plan,
                err_text=err_text,
                trace_sum=trace_sum,
                lesson_text=lesson_text,
                scene=scene,
                title=title,
                case_texts=case_texts,
            )
            new_code = LLMBase.sanitize_generated_code(new_code) or new_code
            if not str(new_code or '').strip():
                raise RuntimeError('修复代理返回空代码')
            note = '自动修复版本'
        except Exception as exc:  # noqa: BLE001
            repair_error = str(exc)
            degraded = True
            new_code = code_text
            note = f'自动修复失败，保留基线代码：{repair_error[:160]}'

        ver = CodeVersion(
            task_id=task_id,
            ver_no=next_ver_no,
            ver_type="repair",
            parent_id=parent_ver_id,
            code_text=new_code,
            code_hash=sha256(new_code.encode("utf-8")).hexdigest(),
            note=note,
        )
        saved = add_version(db, ver)
        return FixVersionResult(
            ver=saved,
            repair_source=getattr(agent, 'last_source', ''),
            repair_error=repair_error or getattr(agent, 'last_error', ''),
            degraded=degraded,
        )
