"""生成服务，负责封装对应业务域的核心流程。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.orm import Session

from app.agent.gen_agent import GenAgent
from app.llm.base import LLMBase
from app.models.case import TestCase
from app.models.ver import CodeVersion
from app.repo.task_repo import add_version, get_latest_version, get_task, replace_cases, list_cases
from app.svc.model_svc import resolve_llm_client
from app.utils.case_block import normalize_case_rows


@dataclass
class GenInitResult:
    ver: CodeVersion
    generated_cases: list[dict]
    gen_source: str = 'fallback'
    case_source: str = 'manual'


class GenService:
    def gen_init_code(self, db: Session, task_id: int, *, auto_gen_cases: bool = False, case_cfg: dict | None = None) -> GenInitResult:
        task = get_task(db, task_id)
        if not task:
            raise ValueError('任务不存在')
        agent = GenAgent(client=resolve_llm_client(db, user_id=task.user_id, model_id=task.model_id))

        existing_case_texts = [str(x.assert_text or '').strip() for x in list_cases(db, task_id) if str(x.assert_text or '').strip()]
        latest = get_latest_version(db, task_id)
        if latest:
            # 兼容早期 bundle 解析失败造成的“代码 + cases JSON 尾巴”污染。
            sanitized = LLMBase.sanitize_generated_code(latest.code_text or '')
            if sanitized and sanitized != (latest.code_text or ''):
                latest.code_text = sanitized
                latest.code_hash = sha256(sanitized.encode('utf-8')).hexdigest()
                db.add(latest)
                db.commit()
                db.refresh(latest)

            # 已有初始版本时，不重复生成代码；若勾选 AI 用例且当前还没有 case，可补一次测试用例。
            if auto_gen_cases:
                bundle = agent.run(task.problem_text, task.scene, title=task.title, auto_gen_cases=True, case_cfg=case_cfg or {}, case_texts=existing_case_texts)
                generated_cases = bundle.cases or []
                if generated_cases:
                    self._replace_task_cases(db, task_id, generated_cases)
                    return GenInitResult(ver=latest, generated_cases=generated_cases, gen_source='cached', case_source=bundle.source)
            return GenInitResult(ver=latest, generated_cases=[], gen_source='cached', case_source='manual')

        bundle = agent.run(
            task.problem_text,
            task.scene,
            title=task.title,
            auto_gen_cases=bool(auto_gen_cases),
            case_cfg=case_cfg or {},
            case_texts=existing_case_texts,
        )
        code_text = LLMBase.sanitize_generated_code(bundle.code_text) or bundle.code_text
        ver = CodeVersion(
            task_id=task.id,
            ver_no=1,
            ver_type='init',
            parent_id=None,
            code_text=code_text,
            code_hash=sha256(code_text.encode('utf-8')).hexdigest(),
            note='初始生成版本',
        )
        ver = add_version(db, ver)

        generated_cases = bundle.cases or []
        if auto_gen_cases and generated_cases:
            self._replace_task_cases(db, task_id, generated_cases)

        return GenInitResult(
            ver=ver,
            generated_cases=generated_cases,
            gen_source=bundle.source,
            case_source=bundle.source if generated_cases else 'manual',
        )

    @staticmethod
    def _replace_task_cases(db: Session, task_id: int, generated_cases: list[dict]):
        task = get_task(db, task_id)
        scene = str(task.scene or 'func') if task else 'func'
        rows: list[TestCase] = []
        for idx, item in enumerate(generated_cases, start=1):
            rows.append(
                TestCase(
                    task_id=task_id,
                    src_type=str(item.get('src_type') or 'ai'),
                    case_in=item.get('case_in'),
                    expect_out=item.get('expect_out'),
                    assert_text=str(item.get('assert_text') or '').strip(),
                    weight=float(item.get('weight') or 1.0),
                    sort_no=int(item.get('sort_no') or idx),
                )
            )
        norm_rows = [
            TestCase(
                task_id=task_id,
                src_type=x.src_type,
                case_in=x.case_in,
                expect_out=x.expect_out,
                assert_text=x.assert_text,
                weight=x.weight,
                sort_no=x.sort_no,
            )
            for x in normalize_case_rows(scene, rows)
        ]
        replace_cases(db, task_id, norm_rows)
