"""回退决策服务，负责封装对应业务域的核心流程。"""

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.ver import CodeVersion
from app.repo.task_repo import add_version


@dataclass
class RollbackDecision:
    """回滚决策结果。"""

    action: str
    reason: str
    stagnation_cnt: int


class RollbackService:
    """真正的基线回退服务。

    这一版不再只是维护 best_score / best_ver_id 两个字段，而是显式区分：
    1. 历史最优版本（best_ver_id / best_score）
    2. 当前尝试版本（本轮刚运行完的代码）
    3. 下一轮修复基线（可能是当前版本，也可能是回滚版本）

    设计目标：
    - 只有“严格提升”时才更新最佳基线，避免同分版本不断覆盖 best；
    - 参考 TraceCoder 的 accept / continue / rollback 三态；
    - 发生明显回退时，真正落一个 rollback 版本，后续修复从该基线继续。
    """

    def sync_best(self, db: Session, task: Task, ver_id: int, score: float) -> bool:
        """仅在严格提升时刷新最佳基线。

        返回值表示本次是否真的刷新了 best_ver_id / best_score。
        首次运行时，即便 score=0，也会把当前版本登记为首个基线。
        """
        improved = task.best_ver_id is None or score > float(task.best_score or 0.0)
        if improved:
            task.best_score = score
            task.best_ver_id = ver_id
            db.commit()
            db.refresh(task)
        return improved

    def decide(
        self,
        task: Task,
        attempted_score: float,
        previous_score: float | None,
        stagnation_cnt: int,
    ) -> RollbackDecision:
        """按当前得分、历史最优得分、上一轮得分做三态决策。"""
        best_known = float(task.best_score or 0.0)

        # 首次尝试还没有 best 基线，直接接纳为当前最佳起点。
        if task.best_ver_id is None:
            return RollbackDecision(
                action="accept",
                reason="首次尝试，登记为首个基线版本",
                stagnation_cnt=0,
            )

        # 严格优于历史最优：直接接纳并刷新最佳基线。
        if attempted_score > best_known:
            return RollbackDecision(
                action="accept",
                reason="本轮通过率严格提升，刷新最佳基线",
                stagnation_cnt=0,
            )

        # 与历史最优持平：允许继续从当前版本往下修，但不覆盖最佳基线。
        if attempted_score == best_known:
            return RollbackDecision(
                action="continue",
                reason="本轮与最佳基线持平，继续沿当前版本探索",
                stagnation_cnt=stagnation_cnt + 1,
            )

        # 分数下降且比上一轮更差：真正触发回退到历史最佳基线。
        if previous_score is not None and attempted_score < previous_score and task.best_ver_id:
            return RollbackDecision(
                action="rollback",
                reason="本轮出现明显回退，下一轮切回历史最佳基线",
                stagnation_cnt=stagnation_cnt + 1,
            )

        # 其他情况属于轻度停滞：先保留当前版本，继续尝试一次。
        return RollbackDecision(
            action="continue",
            reason="本轮未优于最佳基线，但尚未出现更严重回退",
            stagnation_cnt=stagnation_cnt + 1,
        )

    def make_rollback_version(
        self,
        db: Session,
        task_id: int,
        rollback_to: CodeVersion,
        from_ver_id: int,
        next_ver_no: int,
        note: str | None = None,
    ) -> CodeVersion:
        """显式创建 rollback 版本，让版本链真正留下“回退节点”。"""
        new_code = rollback_to.code_text or ""
        ver = CodeVersion(
            task_id=task_id,
            ver_no=next_ver_no,
            ver_type="rollback",
            # parent_id 指向“发生回退的失败版本”，方便在版本树中看到回退来源。
            parent_id=from_ver_id,
            code_text=new_code,
            code_hash=sha256(new_code.encode("utf-8")).hexdigest() if new_code else None,
            note=note or f"回退到 v{rollback_to.ver_no} 作为修复基线",
        )
        return add_version(db, ver)
