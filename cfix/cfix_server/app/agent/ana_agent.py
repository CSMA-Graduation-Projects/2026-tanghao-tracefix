from __future__ import annotations

from collections import Counter
import re

from app.core.cfg import settings
from app.llm.base import LLMBase
from app.llm.factory import get_llm_client
from app.llm.prompt import build_analysis_prompt
from app.utils.fail_focus import (
    build_case_clue_text,
    build_focus_guidance_from_err,
    classify_file_failure,
    parse_fail_case_ids,
    parse_focus_summary,
    parse_lesson_stats,
)
from app.utils.api_contract import build_case_behavior_guard, build_case_contract_guard


class AnaAgent:
    """分析代理：输出 root_cause / fix_plan / inst_sugg。"""

    def __init__(self, client=None):
        self.client = client if client is not None else (get_llm_client() if settings.llm_ready else None)
        self.last_source = "init"
        self.last_error = ""

    @staticmethod
    def _coerce_from_text(raw: str) -> dict:
        text = (raw or '').strip()
        data: dict[str, str] = {}
        for key in ('root_cause', 'fix_plan', 'inst_sugg'):
            marker = key + ':'
            idx = text.lower().find(marker)
            if idx >= 0:
                rest = text[idx + len(marker):].strip()
                data[key] = rest.split('\n', 1)[0].strip()
        return data

    @staticmethod
    def _has_noise(msg: str | None) -> bool:
        s = (msg or '')
        markers = ['cfix_emit', 'cfix_short', '_MatchResult__cfix_emit', '_MatchResult__cfix_short', "name 'token' is not defined"]
        return any(m in s for m in markers)

    @staticmethod
    def _cluster_from_line(line: str) -> str | None:
        s = (line or '').lower()
        if not s:
            return None
        if any(k in s for k in ('topo_sort', '字典序', '最小堆')):
            return 'graph_order'
        if any(k in s for k in ('can_finish', '缺失依赖', 'missing', '环', 'cycle')):
            return 'graph_validation'
        if any(k in s for k in ('blocked_count', 'ready(', 'done 快照', '重复依赖')):
            return 'graph_ready_count'
        if any(k in s for k in ('batch_apply', 'object(), []', 'unknown', 'empty tuple', 'non-empty tuple', '错误 engine', '错误 engine 类型')):
            return 'config_batch_api'
        if any(k in s for k in ('push_scope', 'pop_scope', 'freeze_scope', 'unfreeze_scope', 'list_scopes', 'cannot pop root scope', 'frozen scope')):
            return 'config_scope_state'
        if any(k in s for k in ('scopedconfig', 'effective_items', 'itemsr', 'getr', 'render(', 'resolve=true', 'batch_apply', '${host}', '${port}', '$$', '循环引用', "name 'resolve' is not defined")):
            return 'config_resolver'
        if 'normalize_topic' in s or 'validate_pattern' in s or 'topic_matches' in s:
            return 'match_validate'
        if 'list_subscriptions' in s or 'count(' in s:
            return 'list_count'
        if 'once_' in s or 'once=' in s or 'once_bad' in s or 'once_ok' in s or 'r81' in s or 'r82' in s:
            return 'once_semantics'
        if 'errors ==' in s or 'collect_errors' in s or 'bad7' in s or 'ok7' in s or 'runtimeerror:' in s or 'keyerror:' in s or 'valueerror:' in s:
            return 'error_collection'
        if 'stopper' in s or 'stop_h' in s or 'r5 =' in s or 'return stop' in s:
            return 'stop_semantics'
        if 'called ==' in s or 'results ==' in s or 'order ==' in s or 'emit(' in s or 'subscribe(' in s:
            return 'dispatch_order'
        return None

    @classmethod
    def _extract_fail_clusters(cls, err_text: str, lesson_text: str = '') -> list[str]:
        lines = [x.strip() for x in (err_text or '').splitlines() if x.strip()]
        cnt: Counter[str] = Counter()
        for tag in parse_focus_summary(err_text):
            cnt[tag] += 2
        for line in lines:
            if cls._has_noise(line):
                continue
            c = cls._cluster_from_line(line)
            if c:
                cnt[c] += 1
        if 'case#' in (err_text or '').lower() and 'snippet:' in (err_text or '').lower():
            for raw in re.findall(r'case#\d+.*?snippet:\s*(.+)', err_text or '', flags=re.I):
                guessed = classify_file_failure(raw, err_text)
                if guessed:
                    cnt[guessed] += 1
        lesson_info = parse_lesson_stats(lesson_text)
        for tag in lesson_info['repeated_tags']:
            cnt[tag] += 2
        if lesson_info['oscillation']:
            cnt['repair_oscillation'] += 3
        return [k for k, _v in cnt.most_common()]

    @staticmethod
    def _cluster_case_ids(err_text: str, lesson_text: str = '') -> list[int]:
        ids = parse_fail_case_ids(err_text)
        lesson_info = parse_lesson_stats(lesson_text)
        ids.extend(int(x) for x in lesson_info.get('repeated_case_ids', []) if isinstance(x, int))
        seen = set()
        out = []
        for x in ids:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    @staticmethod
    def _scene_fallback(err_text: str, scene: str = 'func', lesson_text: str = '', case_texts: list[str] | None = None) -> dict:
        root = '当前为占位分析：系统检测到代码未通过测试，需要结合错误与轨迹进一步定位。'
        plan = '优先检查函数返回值、边界条件和断言失败对应的逻辑分支。'
        msg = err_text or ''
        if scene == 'class':
            root = '类文件级任务当前未通过，通常表示构造函数、对象状态维护或公开方法之间的协作逻辑存在问题。'
            plan = '对照失败样例检查类名、构造函数参数、属性更新、返回值，以及多个方法连续调用后的状态是否一致。'
        elif scene == 'file':
            api_guard = build_case_contract_guard(msg, case_texts, scene=scene)
            guard = build_focus_guidance_from_err(msg, scene=scene, lesson_text=lesson_text)
            if guard:
                if api_guard:
                    guard['root_cause'] = (guard.get('root_cause') or '') + '\n' + api_guard
                    guard['fix_plan'] = (guard.get('fix_plan') or '') + '\n' + api_guard
                return guard
            case_ids = AnaAgent._cluster_case_ids(err_text, lesson_text)
            case_tip = f' 近期稳定失败用例：{", ".join(f"case#{x}" for x in case_ids[:6])}。' if case_ids else ''
            case_clues = build_case_clue_text(err_text, scene)
            root = '模块级任务当前未通过，通常表示多个公开 API 之间的协作、排序、状态维护或输入校验契约没有统一。' + case_tip
            low_msg = (err_text or '').lower()
            has_list_evidence = 'list_subscriptions' in low_msg or 'count("' in low_msg or "count('" in low_msg or 'user.deleted' in low_msg or 'system.boot' in low_msg
            if all(k in low_msg for k in ('user.created', 'task.done', 'list_subscriptions')) or (has_list_evidence and ('exact' in low_msg and 'single' in low_msg and 'tail' in low_msg) and ('stopper' in low_msg or 'late' in low_msg)):
                root += ' 当前失败更像是“样例驱动契约”没有被识别：emit 的顺序必须优先满足可执行样例（例如 exact/tail/single/global 一类序列）；只有在当前失败样例已直接覆盖 list_subscriptions(topic)/count 时，才继续判断它们是否真的需要共享同一个排序键。' 
            elif ('exact' in low_msg and 'single' in low_msg and 'tail' in low_msg) and ('stopper' in low_msg or 'late' in low_msg):
                root += ' 当前失败更像是 emit 的优先级键方向写反：先围绕 user.created 这个可执行样例收口，手工验证 exact > tail > single > global，不要在没有直接样例证据时把 list/count 混入主因。' 
            if case_clues:
                root += ' 失败样例已经暴露出更具体的公共线索，应优先按这些线索收口，而不是继续追单条噪声。'
            plan = '优先按失败簇检查公开 API 的协作关系，避免只修单条断言。'
            if case_clues:
                plan += '\n来自失败样例的线索：\n' + case_clues
            if api_guard:
                root += '\n' + api_guard
                plan += '\n' + api_guard
        elif 'AssertionError' in msg:
            root = '断言失败，通常表示返回结果与预期不一致，优先检查条件判断、边界值和返回值。'
            plan = '根据失败断言对照题意，修正核心条件表达式或返回结果构造逻辑。'
        return {
            'root_cause': root,
            'fix_plan': plan,
            'inst_sugg': '记录关键变量、分支结果、候选排序顺序与返回值。',
        }

    @classmethod
    def _llm_hits_clusters(cls, data: dict, clusters: list[str], lesson_text: str = '') -> bool:
        if not clusters:
            return True
        text = f"{data.get('root_cause', '')}\n{data.get('fix_plan', '')}".lower()
        hints = {
            'dispatch_order': ['emit', 'called', 'results', 'errors', '排序', '顺序', 'priority', '注册顺序', '过滤后按注册顺序', 'exact', 'single', 'tail', 'global', '样例优先', '题目样例优先', '不要强行共用排序键', 'exact/tail/single/global', '更长前缀', 'tail 可以先于 single'],
            'stop_semantics': ['stop', '中断', '停止传播', 'stopper', '先于 late', '顺序导致 stop', '先调度 stopper'],
            'once_semantics': ['once', '移除', '异常时不能移除', '成功后移除', '失败后保留'],
            'error_collection': ['collect_errors', 'errors', '继续分发', '异常', 'results 只保留成功', 'called 记录全部调用'],
            'list_count': ['list_subscriptions', 'count', '过滤', '排序', '注册顺序', '匹配顺序', '展示顺序', '显示顺序', 'emit 与 list 拆开', 'count 只做过滤'],
            'match_validate': ['normalize_topic', 'validate_pattern', 'topic_matches'],
            'graph_order': ['topo_sort', '字典序', '最小堆', '候选节点', '依赖去重'],
            'graph_validation': ['can_finish', '缺失依赖', '环', '非法依赖', '一致性'],
            'graph_ready_count': ['blocked_count', 'ready', 'done 快照', '重复依赖', '未完成任务'],
            'module_api_contract': ['公开 api', '模块契约', '共享契约', '跨 api', '共享 resolver', '终止性', '循环引用', 'effective_items', 'batch_apply', '作用域可见性', 'render', '缺失引用保持原样', '$$', '统一 helper', '剩余公开语义', '批量接口异常语义'],
            'config_resolver': ['resolver', '共享解析器', 'render', 'get(resolve=true)', 'effective_items', '缺失引用保持原样', '$$', '循环引用', '终止性'],
            'config_scope_state': ['push_scope', 'pop_scope', 'freeze_scope', 'unfreeze_scope', 'list_scopes', '顶部 scope', 'root 保护', 'cannot pop root scope', '冻结写保护'],
            'config_batch_api': ['batch_apply', '未知操作', '空 tuple', '错误 engine 类型', '直接抛异常', '结果列表'],
            'repair_oscillation': ['共同失败簇', '不要只改单个排序字段', '振荡', '来回', '停滞'],
        }
        hit_cnt = 0
        for c in clusters[:3]:
            kws = hints.get(c, [])
            if any(k.lower() in text for k in kws):
                hit_cnt += 1
        lesson_info = parse_lesson_stats(lesson_text)
        if lesson_info['oscillation'] and hit_cnt < 2:
            return False
        if lesson_info['stagnation'] and len(clusters) >= 2 and hit_cnt < 2:
            return False
        if 'normalize_topic' in text and 'match_validate' not in clusters:
            return False
        if any(k in text for k in ('emit', 'list_subscriptions', 'collect_errors')) and not any(c in clusters for c in ['dispatch_order', 'stop_semantics', 'once_semantics', 'error_collection', 'list_count', 'match_validate']):
            return False
        if any(k in text for k in ('topo_sort', 'taskgraph', 'blocked_count', 'can_finish')) and not any(c in clusters for c in ['graph_order', 'graph_validation', 'graph_ready_count', 'module_api_contract']):
            return False
        return hit_cnt >= 1

    def run(
        self,
        problem_text: str,
        code_text: str,
        err_text: str,
        trace_sum: str = '',
        lesson_text: str = '',
        scene: str = 'func',
        title: str = '',
        case_texts: list[str] | None = None,
    ) -> dict:
        clusters = self._extract_fail_clusters(err_text, lesson_text)
        fallback = self._scene_fallback(err_text, scene=scene, lesson_text=lesson_text, case_texts=case_texts)

        if not self.client:
            self.last_source = 'fallback'
            self.last_error = 'LLM 未启用'
            return fallback

        prompt = build_analysis_prompt(
            problem_text=problem_text,
            code_text=code_text,
            err_text=err_text,
            trace_sum=trace_sum,
            lesson_text=lesson_text,
            scene=scene,
            fail_clusters=clusters,
            fail_case_ids=self._cluster_case_ids(err_text, lesson_text),
            title=title,
            case_texts=case_texts,
        )
        try:
            raw = self.client.chat(prompt, system_prompt='You are a debugging analysis assistant.')
            try:
                data = LLMBase.extract_json_obj(raw)
            except Exception:
                data = self._coerce_from_text(raw)
            if not isinstance(data, dict):
                data = {}
            if scene == 'file' and not self._llm_hits_clusters(data, clusters, lesson_text=lesson_text):
                self.last_source = 'fallback'
                self.last_error = 'analysis_cluster_miss'
                return fallback
            self.last_source = 'llm'
            self.last_error = '' if data else 'analysis_json_fallback'
            return {
                'root_cause': data.get('root_cause') or fallback['root_cause'],
                'fix_plan': data.get('fix_plan') or fallback['fix_plan'],
                'inst_sugg': data.get('inst_sugg') or '记录关键变量、分支结果、候选排序顺序与返回值。',
            }
        except Exception as exc:  # noqa: BLE001
            self.last_source = 'fallback'
            self.last_error = str(exc)
            return fallback
