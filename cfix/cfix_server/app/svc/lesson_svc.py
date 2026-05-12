from sqlalchemy.orm import Session

from app.models.lesson import Lesson
from app.repo.task_repo import add_lesson
from app.utils.fail_focus import extract_focus_tags, parse_fail_case_ids


class LessonService:
    def save_lesson(
        self,
        db: Session,
        task_id: int,
        round_no: int,
        run_id: int | None,
        plan_id: int | None,
        err_text: str,
        fix_plan: str,
        pass_cnt: int = 0,
        total_cnt: int = 0,
        rollback_flag: bool = False,
    ):
        tags = '、'.join(sorted(extract_focus_tags(err_text))) or 'none'
        case_ids = parse_fail_case_ids(err_text)
        case_text = '、'.join(f'case#{x}' for x in case_ids[:6]) if case_ids else 'none'
        # 将当前失败轮次压缩成一条任务内经验，供后续提示词使用。
        lesson = Lesson(
            task_id=task_id,
            round_no=round_no,
            bad_pattern=err_text[:500] if err_text else None,
            lesson_text=(
                f"第{round_no}轮失败；"
                f"错误摘要：{(err_text or '未知错误')[:120]}；"
                f"焦点簇：{tags}；"
                f"失败用例：{case_text}；"
                f"修复策略：{(fix_plan or '无')[:160]}；"
                f"通过情况：{pass_cnt}/{total_cnt}；"
                f"是否回滚：{'是' if rollback_flag else '否'}"
            ),
            from_run_id=run_id,
            from_plan_id=plan_id,
        )
        return add_lesson(db, lesson)
    
