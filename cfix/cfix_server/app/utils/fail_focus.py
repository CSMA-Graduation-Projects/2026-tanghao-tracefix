from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class FailFocus:
    tag: str
    title: str
    reason: str
    fix_hint: str


_FILE_FOCUS = {
    'dispatch_order': FailFocus(
        tag='dispatch_order',
        title='事件分发顺序/结果聚合',
        reason='called/results/errors 的顺序、内容或过滤逻辑与测试预期不一致。',
        fix_hint='优先检查 emit 主链路的调度规则、called/results/errors 的写入时机，以及成功/异常/STOP 三类返回的聚合顺序。若样例已经明确给出 exact/tail/single/global 之类的顺序，应优先把该顺序视为 emit 的权威行为契约，再反推具体匹配优先级；在字面量前缀数量相同的情况下，要显式确认 tail(**) 是否应先于 single(*)。如果使用数值权重、负号或 reverse 排序，务必手工 dry-run 一次 user.created 样例，确认没有把 `**` / `*` 的先后方向写反。若 "**" 匹配伴随 timeout，优先收口为确定性扫描或带记忆化的匹配，而不是继续微调排序字段。',
    ),
    'stop_semantics': FailFocus(
        tag='stop_semantics',
        title='STOP 中断传播',
        reason='返回 STOP 后 stopped、results 或后续分发停止逻辑不符合预期。',
        fix_hint='检查 STOP 返回是否仍写入 results，stopped 是否置 True，以及后续订阅是否被立即终止。若 STOP 用例要求的先后顺序与题目中的排序规则冲突，先核对测试块是否写反了。',
    ),
    'once_semantics': FailFocus(
        tag='once_semantics',
        title='once 订阅生命周期',
        reason='once 订阅在成功/失败后的移除时机不正确。',
        fix_hint='仅在订阅成功执行完成（含返回 STOP）后自动移除；若抛异常则保留。',
    ),
    'error_collection': FailFocus(
        tag='error_collection',
        title='错误收集与继续分发',
        reason='collect_errors=True/False 下的抛错与继续分发逻辑不一致。',
        fix_hint='collect_errors=False 时遇首个异常立即向外抛出；collect_errors=True 时继续后续分发，并将错误写入 errors。',
    ),
    'list_count': FailFocus(
        tag='list_count',
        title='订阅列表/计数规则',
        reason='list_subscriptions 或 count 的排序、过滤、paused 处理与预期不一致。',
        fix_hint='检查 topic=None 与 topic!=None 两种模式；前者按注册顺序返回全部订阅，count(topic) 只做过滤统计。若题目明确写明 emit 与 list_subscriptions(topic) 共用匹配优先级，则二者必须共享同一套排序键；若题目未明确，再依据样例单独核对 topic!=None 的展示顺序，不要凭旧经验盲目拆成两套规则。',
    ),
    'match_validate': FailFocus(
        tag='match_validate',
        title='topic/pattern 规范化与匹配',
        reason='normalize_topic / validate_pattern / topic_matches 或 pattern 合法性逻辑仍有问题。',
        fix_hint='检查空白、连续分隔符、* 与 ** 的位置限制，以及 ** 只允许最后一段且最多一次。',
    ),
    'graph_order': FailFocus(
        tag='graph_order',
        title='拓扑顺序/字典序规则',
        reason='topo_sort 在多可选节点时的字典序选择、依赖去重或输出顺序与预期不一致。',
        fix_hint='优先统一入度计算、重复依赖去重和候选节点的最小字典序选择；topo_sort 与 ready 共享同一排序契约。',
    ),
    'graph_validation': FailFocus(
        tag='graph_validation',
        title='图合法性判断',
        reason='缺失依赖、环检测或 topo_sort/can_finish 的一致性契约不符合预期。',
        fix_hint='把缺失依赖、环检测与空图语义收口到同一套前置校验逻辑，确保 topo_sort 与 can_finish 结果一致。',
    ),
    'graph_ready_count': FailFocus(
        tag='graph_ready_count',
        title='ready/blocked_count 查询语义',
        reason='ready(done) / blocked_count(done) 的 done 快照、重复依赖处理或未完成任务统计与预期不一致。',
        fix_hint='优先检查 done 是否被当作“查询快照”而非隐式累积状态；重复依赖只能算一个前置条件；blocked_count 只统计当前未完成且尚未满足依赖的任务。',
    ),
    'module_api_contract': FailFocus(
        tag='module_api_contract',
        title='模块公开 API 契约',
        reason='完整模块中多个公开 API 的行为约定没有统一，导致断言在协作路径上失败。',
        fix_hint='优先总结多个公开 API 共享的输入/输出/排序/状态契约，不要只修第一条断言；同时要直接阅读测试块里的显式断言，把其中写出的返回值、返回结构、优先级、排序和布尔语义当作行为契约。若失败已表现为 TypeError / AttributeError / NameError，则必须把测试块里的可执行调用方式当作真实接口契约来适配代码，禁止建议修改测试调用方式。',
    ),
    'config_resolver': FailFocus(
        tag='config_resolver',
        title='配置解析 resolver / 可见视图语义',
        reason='render、get(resolve=True)、effective_items(resolve=True) 的共享解析语义、终止性或可见视图规则不一致。',
        fix_hint='优先统一 resolver：缺失引用保持原样、$$ 还原、循环引用抛 ValueError，并保证 effective_items(resolve=True) 基于最终可见视图解析。',
    ),
    'config_scope_state': FailFocus(
        tag='config_scope_state',
        title='作用域栈 / 冻结状态语义',
        reason='push/pop/freeze/unfreeze/set/delete/list_scopes 的顶部 scope 状态模型不一致，导致 scope 深度、冻结写保护或恢复逻辑漂移。',
        fix_hint='优先统一 scope 栈语义：push_scope 不能复用 pop 的 root 保护；pop_scope 只禁止弹 root；freeze/unfreeze/set/delete/list_scopes 必须围绕当前顶部 scope 使用同一状态模型。',
    ),
    'config_batch_api': FailFocus(
        tag='config_batch_api',
        title='批量接口 / 参数校验语义',
        reason='batch_apply 对非法输入的抛错时机、结果追加顺序或委托到公开 API 的方式不一致。',
        fix_hint='优先保证 batch_apply 在执行前做参数校验：错误 engine、空 tuple、未知操作应直接抛异常；合法操作再顺序追加结果。',
    ),
}


_EXCEPTION_HINTS = ('runtimeerror:', 'valueerror:', 'keyerror:', 'typeerror:', 'attributeerror:')


def _snippet_of(case_text: str, limit: int = 140) -> str:
    src = (case_text or '').strip().replace('\n', ' | ')
    return src if len(src) <= limit else src[: limit - 3] + '...'


def _extract_assert_examples(text: str, limit: int = 3) -> list[str]:
    items: list[str] = []
    for m in re.finditer(r'assert\s+([^\n]+)', text or '', re.I):
        expr = (m.group(1) or '').strip()
        if not expr or expr in {'ok is True', 'ok is False'}:
            continue
        expr = _snippet_of('assert ' + expr, 170)
        if expr not in items:
            items.append(expr)
        if len(items) >= limit:
            break
    return items


def _has_any(text: str, patterns: Iterable[str]) -> bool:
    return any(p in text for p in patterns)


def _looks_like_eventbus(text: str) -> bool:
    low = (text or '').lower()
    return any(k in low for k in (
        'emit(', 'subscribe(', 'list_subscriptions', 'normalize_topic', 'validate_pattern', 'topic_matches',
        'collect_errors', 'stopper', 'once_', 'system.boot', 'user.created', 'user.deleted', 'paused',
    ))


def _looks_like_taskgraph(text: str) -> bool:
    low = (text or '').lower()
    return any(k in low for k in ('topo_sort', 'can_finish', 'taskgraph', 'blocked_count', 'ready('))



def _looks_like_routertable(text: str) -> bool:
    low = (text or '').lower()
    return any(k in low for k in (
        'routertable', 'routenotfounderror', 'routeconflicterror', 'reversebuilderror',
        '/users/<', '/assets/', '/download/', '/method/test', 'list_routes()', 'reverse(', 'remove(',
    ))

def _looks_like_scopedconfig(text: str) -> bool:
    low = (text or '').lower()
    return any(k in low for k in (
        'scopedconfig', 'normalize_key', 'find_refs', 'effective_items', 'itemsr', 'getr',
        'render("http://${host}:${port}', 'render(', 'resolve=true', 'freeze_scope', 'unfreeze_scope',
        'list_scopes', 'batch_apply', '${host}', '${port}', '$$', 'push_scope', 'pop_scope',
    ))


def classify_file_failure(case_text: str, err_msg: str) -> str:
    """为 file 级失败样例打簇。"""
    text = f"{case_text or ''}\n{err_msg or ''}"
    low = text.lower()

    if _looks_like_taskgraph(text):
        if _has_any(low, ('blocked_count', 'ready([', 'ready([]', "['b', 'b']", '重复依赖', 'done) ==')):
            return 'graph_ready_count'
        if _has_any(low, ('can_finish', "['x']", "['a']}", "['a', 'b']", '== []', 'false', '环', 'missing', '不存在')):
            return 'graph_validation'
        return 'graph_order'

    if _looks_like_eventbus(text):
        if _has_any(low, ('normalize_topic', 'validate_pattern', 'topic_matches')):
            return 'match_validate'
        if _has_any(low, ('once=', 'once_h', 'once_bad', 'once_ok', 'tok3', 'r31', 'r32', 'r81', 'r82')):
            return 'once_semantics'
        if _has_any(low, ('collect_errors', 'bad6', 'never6', 'bad7', 'ok7')):
            return 'error_collection'
        if 'errors ==' in low and _has_any(low, _EXCEPTION_HINTS):
            return 'error_collection'
        if _has_any(low, ('return stop', 'stopper', 'stop_h', 'r5 =')):
            return 'stop_semantics'
        if 'list_subscriptions' in low:
            return 'list_count'
        if _has_any(low, ('count("', "count('", 'count(topic', 'bus9.', 'system.boot', 'user.deleted')):
            return 'list_count'
        if _has_any(low, ('called ==', 'results ==', 'order ==', 'priority=', 'emit(', 'subscribe(')):
            return 'dispatch_order'
        return 'dispatch_order'

    if _looks_like_routertable(text):
        if _has_any(low, ('reverse(', 'reversebuilderror', 'list_routes', 'remove(', 'registration order', '注册顺序', 'method 大小写', 'post', 'delete', 'get')):
            return 'module_api_contract'
        return 'module_api_contract'

    if _looks_like_scopedconfig(text):
        if _has_any(low, ('batch_apply', 'object(), []', '[("unknown",)]', "[('unknown',)]", 'empty tuple', 'non-empty tuple', 'engine must be an instance', 'unknown operation')):
            return 'config_batch_api'
        if _has_any(low, ('push_scope', 'pop_scope', 'freeze_scope', 'unfreeze_scope', 'list_scopes', 'cannot pop root scope', 'frozen scope')):
            return 'config_scope_state'
        if _has_any(low, ('render(', 'resolve=true', 'getr', 'itemsr', 'effective_items', '${host}', '${port}', '${a}', '${b}', '$$', 'cycle', '循环引用', "name 'resolve' is not defined")):
            return 'config_resolver'
        return 'module_api_contract'

    return 'module_api_contract'


def build_file_focus_summary(failed_pack: Iterable[tuple], max_examples: int = 4) -> str:
    items = list(failed_pack)
    if not items:
        return ''

    counter: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for item in items:
        case = item[0]
        rs = item[1]
        case_text = getattr(case, 'assert_text', '') or ''
        err_msg = (getattr(rs, 'err_msg', '') or '') + '\n' + (getattr(rs, 'tb_text', '') or '')
        tag = classify_file_failure(case_text, err_msg)
        counter[tag] += 1
        examples.setdefault(tag, [])
        if len(examples[tag]) < max_examples:
            examples[tag].append(_snippet_of(case_text))

    ordered = counter.most_common()
    lines = ['FILE_FAILURE_FOCUS:']
    for tag, cnt in ordered:
        focus = _FILE_FOCUS.get(tag)
        if not focus:
            continue
        lines.append(f'- {focus.title}（{cnt}条）: {focus.reason}')
        lines.append(f'  建议修复重点：{focus.fix_hint}')
        for ex in examples.get(tag, []):
            lines.append(f'  失败样例片段：{ex}')
    return '\n'.join(lines)


def extract_focus_tags(text: str) -> set[str]:
    src = (text or '').lower()
    tags: set[str] = set()
    kw_map = {
        'dispatch_order': ['分发顺序', 'called', 'results', 'priority', '共享排序契约', '测试预期可能有误', '顺序断言可疑', '题面契约优先'],
        'stop_semantics': ['stop', 'stopped', '中断传播', 'stopper', 'stop 用例可疑', '题面排序与 stop 断言冲突'],
        'once_semantics': ['once', '自动移除', '失败后保留', '成功后移除'],
        'error_collection': ['collect_errors', '继续分发', 'errors', 'results 只保留成功'],
        'list_count': ['list_subscriptions', 'count(topic', '订阅列表', '注册顺序', '匹配顺序', '展示顺序断言可疑', '测试预期可能有误'],
        'match_validate': ['normalize_topic', 'validate_pattern', 'topic_matches', '规范化', 'pattern 合法性'],
        'graph_order': ['topo_sort', '拓扑', '字典序', '最小堆', '候选节点'],
        'graph_validation': ['can_finish', '缺失依赖', '环', '非法依赖', '图合法性'],
        'graph_ready_count': ['blocked_count', 'ready(', 'done 快照', '重复依赖', '未完成任务'],
        'module_api_contract': ['模块公开 api', '公开 api 契约', '模块契约'],
        'config_resolver': ['resolver', '共享解析器', 'placeholder', '缺失引用保持原样', '循环引用', 'effective_items', '$$'],
        'config_scope_state': ['push_scope', 'pop_scope', 'freeze_scope', 'unfreeze_scope', 'list_scopes', 'frozen scope', 'cannot pop root scope', '作用域栈'],
        'config_batch_api': ['batch_apply', '空 tuple', '未知操作', '错误 engine 类型', '直接抛异常'],
    }
    for tag, kws in kw_map.items():
        if any(kw.lower() in src for kw in kws):
            tags.add(tag)
    return tags


def parse_focus_summary(err_text: str) -> list[str]:
    tags: list[str] = []
    for line in (err_text or '').splitlines():
        s = line.strip().lower()
        if not s.startswith('- '):
            continue
        if '错误收集' in s or 'collect_errors' in s:
            tags.append('error_collection')
        elif 'ready/blocked_count' in s or 'done 快照' in s or '重复依赖' in s or 'blocked_count' in s:
            tags.append('graph_ready_count')
        elif '拓扑顺序' in s or '字典序' in s:
            tags.append('graph_order')
        elif '图合法性' in s or 'can_finish' in s:
            tags.append('graph_validation')
        elif '订阅列表' in s or 'list_subscriptions' in s or 'count' in s:
            tags.append('list_count')
        elif 'once' in s:
            tags.append('once_semantics')
        elif 'stop' in s or '中断传播' in s:
            tags.append('stop_semantics')
        elif '规范化' in s or '匹配' in s or 'validate_pattern' in s:
            tags.append('match_validate')
        elif '事件分发顺序' in s or '结果聚合' in s:
            tags.append('dispatch_order')
        elif '配置解析 resolver' in s or 'placeholder resolver' in s or '共享解析器' in s:
            tags.append('config_resolver')
        elif '作用域栈' in s or '冻结状态' in s or 'cannot pop root scope' in s or 'push_scope' in s or 'pop_scope' in s:
            tags.append('config_scope_state')
        elif '批量接口' in s or 'batch_apply' in s:
            tags.append('config_batch_api')
        elif '模块公开 api 契约' in s or '模块契约' in s:
            tags.append('module_api_contract')
    return tags


def parse_fail_case_ids(text: str) -> list[int]:
    ids: list[int] = []
    for m in re.finditer(r'case#(\d+)', text or '', re.I):
        try:
            ids.append(int(m.group(1)))
        except Exception:
            pass
    seen = set()
    ordered: list[int] = []
    for x in ids:
        if x not in seen:
            ordered.append(x)
            seen.add(x)
    return ordered


def _normalize_strategy_text(text: str) -> str:
    s = (text or '').strip().lower()
    if not s:
        return ''
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'第\d+轮', '', s)
    s = re.sub(r'case#\d+', 'case', s)
    return s[:220]


def parse_lesson_stats(lesson_text: str) -> dict:
    txt = lesson_text or ''
    scores: list[tuple[int, int]] = []
    for m in re.finditer(r'通过情况：\s*(\d+)\s*/\s*(\d+)', txt):
        scores.append((int(m.group(1)), int(m.group(2))))

    focus_counter: Counter[str] = Counter()
    case_counter: Counter[int] = Counter()
    strategy_counter: Counter[str] = Counter()
    strategies: list[str] = []
    rollback_flags: list[bool] = []

    for block in txt.split('第'):
        if not block.strip():
            continue
        for t in extract_focus_tags(block):
            focus_counter[t] += 1
        for cid in parse_fail_case_ids(block):
            case_counter[cid] += 1
        m = re.search(r'修复策略：(.+?)(?:；通过情况|$)', block, re.S)
        if m:
            raw = m.group(1).strip()
            strategies.append(raw[:180])
            norm = _normalize_strategy_text(raw)
            if norm:
                strategy_counter[norm] += 1
        rb = re.search(r'是否回滚：\s*(是|否)', block)
        if rb:
            rollback_flags.append(rb.group(1) == '是')

    oscillation = False
    stagnation = False
    if len(scores) >= 3:
        vals = [a for a, _b in scores[:3]]
        stagnation = len(set(vals)) == 1
        diffs = [vals[idx] - vals[idx + 1] for idx in range(len(vals) - 1)]
        oscillation = any(x * y < 0 for x, y in zip(diffs, diffs[1:]))
    if len(rollback_flags) >= 3 and rollback_flags[:3].count(True) >= 2:
        oscillation = True

    repeated_case_ids = [cid for cid, cnt in case_counter.items() if cnt >= 2]
    repeated_strategies = [s for s, cnt in strategy_counter.items() if cnt >= 2]
    return {
        'scores': scores,
        'focus_counter': focus_counter,
        'repeated_tags': [tag for tag, cnt in focus_counter.items() if cnt >= 2],
        'repeated_case_ids': sorted(repeated_case_ids),
        'strategies': strategies,
        'repeated_strategies': repeated_strategies,
        'oscillation': oscillation,
        'stagnation': stagnation,
    }


def _infer_protected_areas(tags: set[str]) -> list[str]:
    areas: list[str] = []
    if any(tag.startswith('graph_') for tag in tags):
        if 'graph_validation' not in tags:
            areas.extend(['_validate_graph', '_validate_and_build_graph', 'can_finish'])
        if 'graph_order' not in tags:
            areas.extend(['topo_sort'])
        if 'graph_ready_count' not in tags:
            areas.extend(['TaskGraph.ready', 'TaskGraph.blocked_count'])
    elif any(tag in tags for tag in ['dispatch_order', 'stop_semantics', 'once_semantics', 'error_collection', 'list_count', 'match_validate']):
        if 'match_validate' not in tags:
            areas.extend(['normalize_topic', 'validate_pattern', 'topic_matches'])
        if 'dispatch_order' not in tags and 'stop_semantics' not in tags and 'once_semantics' not in tags and 'error_collection' not in tags:
            areas.extend(['emit'])
        if 'list_count' not in tags:
            areas.extend(['list_subscriptions', 'count'])
    seen = set()
    out: list[str] = []
    for x in areas:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def derive_file_case_clues(err_text: str) -> list[str]:
    src = err_text or ''
    low = src.lower()
    clues: list[str] = []
    if _looks_like_taskgraph(src):
        if _has_any(low, ('blocked_count', 'ready([', 'ready([]', "['b', 'b']", '重复依赖')):
            clues.append('依赖计数线索：若依赖列表中出现重复前置项，同一依赖通常只能算一个真实前置条件；ready(done) 与 blocked_count(done) 都应基于去重后的依赖集合判断。')
        if _has_any(low, ('topo_sort', "'z': []", "'a': []", "'m': []", '字典序')):
            clues.append('字典序线索：当多个任务同时可执行时，topo_sort 与 ready 都应优先返回字典序更小者，不能受字典遍历顺序或历史状态污染。')
        if _has_any(low, ('can_finish', '== []', 'false', "['x']", '环', 'missing', '不存在')):
            clues.append('合法性线索：缺失依赖、环检测与空图语义必须在 topo_sort 与 can_finish 两个 API 中保持一致；不要一个 API 判非法、另一个 API 仍继续计算。')
        if _has_any(low, ('ready([', 'blocked_count(', 'done)')):
            clues.append('查询语义线索：ready(done) / blocked_count(done) 更像“基于传入 done 快照的纯查询”；若实现里偷偷突变内部 done 状态，很容易在多次调用后把固定用例带偏。')
        return clues

    if _looks_like_routertable(src):
        if _has_any(low, ('routenotfounderror', '/health', '/api/ping', '/users/12', '/files/css', '/download/', '////', 'method: get', 'method: post')):
            clues.append('路径匹配线索：若大量失败都是 RouteNotFoundError，优先检查根路径与多斜杠路径规范化、method 大小写规范化，以及 int/str/path 片段编译后是否真的参与 resolve。')
        if _has_any(low, ('reversebuilderror', 'reverse(', 'list_routes', 'remove(', '/a', '/v1/users', '/v3/users', 'registration order', '注册顺序')):
            clues.append('反向构造/管理线索：reverse(handler, method)、remove(pattern, methods) 与 list_routes 不应各自维护不同的 pattern/method 视图；method 去重/排序/规范化和注册顺序必须在三者中保持一致。')
        if _has_any(low, ('/items/123', '/items/abc', '/assets/index', '/p/x/y', '/same/value')):
            clues.append('优先级线索：resolve 的候选路由排序应统一考虑 priority、静态片段数、参数片段数与注册顺序；若这些权重只在部分分支生效，就会同时打坏 static/dynamic/path 多组 case。')
        return clues

    if _looks_like_scopedconfig(src):
        if _has_any(low, ('render(', 'resolve=true', 'getr', 'itemsr', 'effective_items', '${host}', '${port}', '${a}', '${b}', '$$')):
            clues.append('共享解析器线索：render、get(resolve=True) 与 effective_items(resolve=True) 不应各自实现一套解析逻辑；它们应共享同一个 placeholder resolver，并且 resolver 必须保证单调前进、可终止、对缺失引用保持原样。')
        if _has_any(low, ('timeout', 'container execution timeout', '循环引用', 'valueerror', '${a}', '${b}')):
            clues.append('终止性线索：若 resolver 在缺失引用上反复重试、对同一 key 重复展开、或没有把“访问栈/已在解析中的 key”作为循环检测依据，就会在 render/get(resolve=True) 上卡住直到超时。')
        if _has_any(low, ('effective_items', 'itemsr', 'scope_name', 's1', 's2', 'dev', 'root')):
            clues.append('有效视图线索：effective_items 应基于“当前最终可见视图”逐 key 选出唯一生效值，并保留该值来自哪个 scope；不能简单把所有 scope 线性拼接后再局部改值。')
        if _has_any(low, ('batch_apply', 'expected valueerror', 'unknown', '()', 'typeerror', 'object(), []')):
            clues.append('批量接口线索：batch_apply 的职责是顺序执行并返回结果列表；但对未知操作、空 tuple、错误 engine 类型这类非法输入，应在追加结果前直接抛异常，而不是吞掉后再把异常对象塞进列表。')
        if _has_any(low, ('freeze_scope', 'unfreeze_scope', 'delete(', 'push_scope', 'pop_scope', 'list_scopes', 'cannot pop root scope')):
            clues.append('作用域状态线索：顶部 scope 的冻结、删除和 pop 恢复应共用一套一致的状态模型；尤其 push_scope 不能复用“root 不能 pop”的判断，pop_scope 才负责禁止弹出 root。')
        return clues

    assert_examples = _extract_assert_examples(src)
    if assert_examples:
        clues.append('行为断言线索：测试块已经显式写出 ' + '；'.join(assert_examples[:2]) + '。这些断言本身就是公开 API 的真实行为契约，应让代码直接满足，而不是建议修改测试。')

    has_event_list_evidence = 'list_subscriptions' in low or 'count("' in low or "count('" in low or 'user.deleted' in low or 'system.boot' in low
    if ('res.called ==' in low or 'results ==' in low or 'order ==' in low) and ('user.created' in low or 'emit("user.created"' in low or 'subscribe("user.*"' in low or 'subscribe("user.**"' in low):
        clues.append('分发顺序线索：事件分发顺序这组失败通常不是单个 handler 逻辑错，而是 emit 主链路的调度契约不对；先单独核对 emit 是否应该“先过滤匹配，再按优先级调度”，并用 user.created 样例手工验证最终顺序是否真的是 [exact, tail, single, global]。如果实现里用了数值权重、负号或 reverse 排序，请优先怀疑是优先级方向写反，而不是继续扩展到 list/count 逻辑。')
    if all(k in low for k in ('user.created', 'task.done', 'list_subscriptions')) or (has_event_list_evidence and ('exact' in low and 'single' in low and 'tail' in low) and ('stopper' in low or 'late' in low)):
        clues.append('示例优先线索：若题面里的抽象排序描述与多条可执行样例冲突，应优先以样例约束为准。只有在当前失败样例已经直接覆盖 list_subscriptions(topic)/count 时，才去判断它们是否应与 emit 共享排序键；否则先把 emit/STOP 的样例顺序收口。')
    elif ('exact' in low and 'single' in low and 'tail' in low) and ('stopper' in low or 'late' in low):
        clues.append('示例优先线索：当前稳定失败主要来自 emit/STOP 这组可执行样例，而不是列表展示逻辑。请先把 emit 的权威样例顺序 exact > tail > single > global 跑通，不要在没有直接样例证据时把 list_subscriptions(topic)/count 混入同一轮根因。')
    if 'r5 = bus5.emit' in low or 'stopper' in low:
        clues.append('STOP 线索：STOP 用例失败时，不仅要检查 `ret is STOP` 后是否立即中断，还要先核对 stopper 是否在期望顺序上先于 late handler 被调度。')
    if 'collect_errors' in low or ('errors ==' in low and _has_any(low, _EXCEPTION_HINTS)) or 'r7 = bus7.emit' in low:
        clues.append('错误收集线索：`collect_errors=True` 时 called 应记录所有实际调用的 handler，results 只保留成功返回值，errors 应写成 `(name, "Type: msg")` 风格的结构化摘要。')
    if ('once=' in low or 'once_bad' in low or 'once_ok' in low or 'tok3' in low) and ('r81' in low or 'r82' in low or 'collect_errors' in low or 'r31' in low or 'r32' in low):
        clues.append('once 生命周期线索：once 订阅只能在“本次 handler 成功返回（包括 STOP）”后移除；若抛异常则必须保留，以便下一次 emit 仍会再次触发。')
    if 'list_subscriptions' in low or 'count("' in low or "count('" in low or 'user.deleted' in low:
        clues.append('列表/计数线索：`list_subscriptions(None)` 应按注册顺序返回全量；`count(topic)` 只关心“未 paused 且匹配”的过滤结果；`list_subscriptions(topic)` 的展示顺序要根据失败样例单独核对，不能先验地强绑到 emit 的调度顺序上。')
    return clues


def build_case_clue_text(err_text: str, scene: str) -> str:
    if (scene or '').strip().lower() != 'file':
        return ''
    clues = derive_file_case_clues(err_text)
    if not clues:
        return ''
    return '\n'.join(f'- {item}' for item in clues)


def build_file_joint_hypothesis(err_text: str, lesson_text: str = '') -> str:
    tags = set(parse_focus_summary(err_text)) | extract_focus_tags(err_text)
    info = parse_lesson_stats(lesson_text)
    tags |= set(info['repeated_tags'])
    repeated_cases = set(info['repeated_case_ids'])
    if 'dispatch_order' in tags and 'list_count' in tags and 'stop_semantics' in tags:
        if repeated_cases & {161, 169, 176}:
            return '这些失败更像是“排序契约被过度统一”：emit、STOP 与 list_subscriptions(topic) 可能共享匹配/过滤，但不一定共享同一个排序键；继续只调 `_get_sort_key` 往往会在 dispatch 和 list 之间来回打架。'
        low = (err_text or '').lower()
        has_list_evidence = 'list_subscriptions' in low or 'count("' in low or "count('" in low or 'user.deleted' in low or 'system.boot' in low
        if any(k in low for k in ('user.created', 'task.done', 'exact', 'single', 'tail', 'stopper', 'late')):
            if has_list_evidence:
                return '这些失败更像是“可执行样例优先于抽象排序说明”：emit 与 STOP 应优先满足样例里写死的行为顺序（例如 exact/tail/single/global）；只有在当前失败样例已直接覆盖 list_subscriptions(topic)/count 时，才继续判断它们是否真的应该共用同一个排序键。'
            return '这些失败更像是“emit 的优先级键实现方向写反了”：当前直接失败的是 emit/STOP 样例，而不是 list/count。请先围绕 user.created 样例手工 dry-run，确认 exact > tail > single > global 是否真的成立；若实现里用了数值权重、负号或 reverse 排序，优先怀疑是 `**` / `*` 的先后方向被翻转。'
    if 'dispatch_order' in tags and 'list_count' in tags:
        return '这些失败更像是匹配/过滤与排序职责没有拆开：先确认 count(topic) 只做过滤，再分别核对 emit 的调度顺序和 list_subscriptions(topic) 的展示顺序，避免错误地强行共用一个全局排序规则。'
    if 'once_semantics' in tags and 'error_collection' in tags:
        return '这些失败更像是 once 与 collect_errors 的状态流转不一致：成功返回与异常路径的移除时机需要完全分开处理。'
    if 'graph_validation' in tags and ('graph_order' in tags or 'graph_ready_count' in tags):
        return '这些失败更像是同一套图契约没有收口：依赖去重、合法性判断、字典序选择与 ready/blocked_count 的 done 语义没有统一，导致 topo_sort/can_finish/TaskGraph 三组 API 表现分裂。'
    if 'graph_ready_count' in tags and 'graph_order' in tags:
        return '这些失败更像是“候选节点选择 + done 快照语义”同时失配：一旦内部状态被错误累积或重复依赖被重复计数，ready、blocked_count 与 topo_sort 的顺序契约会一起漂移。'
    low = (err_text or '').lower()
    if _looks_like_routertable(err_text) or any(k in low for k in ('routenotfounderror', 'reversebuilderror', 'routeconflicterror', '/users/12', '/assets/index', '/download/')):
        return '这些失败更像是“路由主契约没有收口”：路径规范化、method 规范化、pattern 编译、候选路由优先级、reverse/remove/list_routes 视图并没有共享同一套核心规则。若继续只修某一个 path case 或某一个 reverse 分支，往往会在 resolve / reverse / remove 之间来回打架。'

    if _looks_like_scopedconfig(err_text) or any(k in low for k in ('render(', 'effective_items', 'itemsr', 'getr', 'resolve=true', 'batch_apply', 'push_scope', 'pop_scope', 'freeze_scope', 'list_scopes', '${host}', '${port}')):
        if repeated_cases & {34, 35, 36, 37}:
            return '这些失败更像是“作用域栈状态模型没有收口”：push_scope、pop_scope、freeze/unfreeze、delete 与 list_scopes 没有围绕同一套顶部 scope 语义工作。尤其出现 `cannot pop root scope` 时，先检查是否把 push_scope 的守卫条件写成了 pop_scope 的 root 保护。'
        if repeated_cases & {31, 39} and 32 not in repeated_cases:
            return '这些失败更像是“共享 helper 已部分修通，但剩余公开契约仍未收口”：render 仍没有完全复用统一 resolver（尤其是缺失引用保持原样、$$ 转义和 render/effective_items 的一致性），而 batch_apply 仍在非法输入上吞异常并继续返回列表。此时不应继续重写循环检测主逻辑，而应优先修剩余的共享字符串解析语义和批量接口异常语义。'
        if repeated_cases & {31, 33, 39} or repeated_cases & {18, 20, 26}:
            return '这些失败更像是“统一 resolver 的剩余公开语义仍然不一致”：一部分 API 可能已经共享了解析 helper，但 render / get(resolve=True) / effective_items(resolve=True) 对缺失引用、$$ 还原、循环引用和当前有效视图的公开语义仍没有完全收口；与此同时 batch_apply 还应把非法输入当作直接异常而不是普通结果。此时最稳妥的方向是保留已转绿的路径，围绕统一 resolver 的最终公开语义与批量接口异常语义做模块级收口。'
        if 'cannot pop root scope' in low and 'push_scope' in low:
            return '这些失败更像是 push/pop 守卫条件写反：push_scope 不应检查“root 不能 pop”，它只负责压入新 scope；root 保护只应出现在 pop_scope。'
        return '这些失败更像是“共享解析 helper 没有真正收口”：render、get(resolve=True)、effective_items(resolve=True) 应共享同一个 resolver；一旦 resolver 的终止性、循环检测、缺失引用策略或 $$ 转义语义不一致，就会同时出现 timeout、循环引用判定错误和 itemsr 断言失败。'
    return ''


def build_focus_guidance_from_err(err_text: str, scene: str, lesson_text: str = '') -> dict[str, str] | None:
    if (scene or '').strip().lower() != 'file':
        return None
    tags = set(parse_focus_summary(err_text)) | extract_focus_tags(err_text)
    lesson_info = parse_lesson_stats(lesson_text)
    tags |= set(lesson_info['repeated_tags'])
    if not tags:
        return None

    ordered = [tag for tag, _ in Counter(parse_focus_summary(err_text) + list(tags)).most_common()]
    top_tags = ordered[:3]
    focus_lines = []
    for tag in top_tags:
        focus = _FILE_FOCUS.get(tag)
        if focus:
            focus_lines.append(f'- {focus.title}: {focus.fix_hint}')

    protected = _infer_protected_areas(tags)
    guard = ''
    if protected:
        guard = '本轮非重点区域（除非错误簇明确指向）请尽量保持不变：' + '、'.join(protected) + '。'

    stable_cases = lesson_info['repeated_case_ids']
    stable_case_text = f"最近多轮稳定失败用例：{', '.join('case#'+str(x) for x in stable_cases[:6])}。" if stable_cases else ''
    repeated_strategy_text = ''
    if lesson_info['repeated_strategies']:
        repeated_strategy_text = '最近多轮修复策略高度重复，说明系统容易围绕同一局部点来回补丁。'
        if any('_get_sort_key' in s or '排序' in s for s in lesson_info['repeated_strategies']):
            repeated_strategy_text += ' 其中多轮都在调整同一个排序键，说明问题很可能不是“再改一次排序字段”就能解决，而是 emit / list / count 的职责边界本身被混在了一起。'
    joint = build_file_joint_hypothesis(err_text, lesson_text)
    case_clues = derive_file_case_clues(err_text)

    low_err = (err_text or '').lower()
    order_only_eventbus = (
        _looks_like_eventbus(err_text)
        and 'exact' in low_err and 'tail' in low_err and 'single' in low_err and 'global' in low_err
        and 'task.done' not in low_err and 'stopper' not in low_err and 'late' not in low_err
        and 'list_subscriptions' not in low_err and 'count("' not in low_err and "count('" not in low_err
    )

    if lesson_info['oscillation'] or lesson_info['stagnation']:
        root = '文件级复杂任务在最近多轮里通过数没有提升，说明当前修复已出现停滞/振荡；需要停止围绕单一局部条件来回修改，转而同时处理主要失败簇。'
    else:
        root = '文件级复杂任务当前存在多个共同失败簇，应优先修正能同时解释多条失败样例的公共逻辑，而不是只修单条断言。'
    if _looks_like_scopedconfig(err_text):
        root += ' 当前更像是共享解析器、作用域可见性与批量接口语义没有在模块内部统一，导致多个公开 API 同时漂移。'
        if set(lesson_info.get('repeated_case_ids', [])) & {31, 39} and 32 not in set(lesson_info.get('repeated_case_ids', [])):
            root += ' 当前稳定剩余失败已收敛到 render 与 batch_apply 两条公开契约：前者通常是缺失引用/$$ 转义/统一 resolver 语义仍不一致，后者通常是非法输入没有直接抛错。'
            root += ' 这类场景更适合做“剩余公开语义收口”，而不是继续为已经转绿的循环检测路径做大改。'
    if repeated_strategy_text:
        root += repeated_strategy_text
    if joint:
        root += joint

    plan = '本轮请按失败簇做模块级修复，优先级如下：\n' + ('\n'.join(focus_lines) if focus_lines else '先检查模块公开 API 的共享契约。')
    if case_clues:
        plan += '\n来自失败样例的具体线索：\n' + '\n'.join(f'- {item}' for item in case_clues)
    if lesson_info['oscillation'] or lesson_info['stagnation'] or repeated_strategy_text:
        plan += '\n额外约束：最近多轮通过数未提升或策略重复，必须同时处理主失败簇，不要继续只改单个 if 条件或单个排序字段。'
    if _looks_like_scopedconfig(err_text) and set(lesson_info.get('repeated_case_ids', [])) & {31, 39}:
        plan += '\nScopedConfig 定向收口：如果 case#32/循环引用类用例已经通过，就不要继续大改循环检测；请集中修复 render 与 effective_items 对统一 resolver 的复用、缺失引用保持原样、$$ 还原，以及 batch_apply 的非法输入抛错语义。'
    if stable_case_text:
        plan += '\n' + stable_case_text
    if guard:
        plan += '\n' + guard
    return {
        'root_cause': root,
        'fix_plan': plan,
        'inst_sugg': '优先记录共享契约相关变量：候选节点/候选订阅排序、done 快照、依赖去重结果、called/results/errors 写入顺序，以及 list/count/拓扑输出是否复用同一过滤与排序结果。',
    }


def build_file_fix_guard(err_text: str, lesson_text: str = '') -> str:
    tags = set(parse_focus_summary(err_text)) | extract_focus_tags(err_text)
    lesson_info = parse_lesson_stats(lesson_text)
    tags |= set(lesson_info['repeated_tags'])
    protected = _infer_protected_areas(tags)
    parts: list[str] = []
    if lesson_info['repeated_case_ids']:
        parts.append('最近多轮稳定失败的用例集中在：' + '、'.join(f'case#{x}' for x in lesson_info['repeated_case_ids'][:6]) + '。')
    if lesson_info['stagnation']:
        parts.append('最近多轮通过数没有提升，禁止继续重复同一局部补丁。')
    if lesson_info['repeated_strategies']:
        parts.append('最近多轮修复策略高度重复，说明需要从更高层的共享契约入手，而不是重复历史修法。')
    joint = build_file_joint_hypothesis(err_text, lesson_text)
    if joint:
        parts.append(joint)
    clues = derive_file_case_clues(err_text)
    if clues:
        parts.append('失败样例直接提示：' + ' '.join(clues[:3]))
    if _looks_like_scopedconfig(err_text) and (set(lesson_info.get('repeated_case_ids', [])) & {31, 39} or set(lesson_info.get('repeated_case_ids', [])) & {18, 26}):
        parts.append('若循环引用/timeout 用例已转绿，请禁止继续围绕 `_resolve` 的大改写反复试错；优先修复 render / get(resolve=True) / effective_items(resolve=True) 对统一 resolver 的最终公开语义、缺失引用与 $$ 语义，以及 batch_apply 的前置参数校验与直接抛错。')
    if _looks_like_scopedconfig(err_text) and set(lesson_info.get('repeated_case_ids', [])) & {34, 35, 36, 37}:
        parts.append('若多轮稳定失败集中在 push/pop/freeze/list_scopes 相关 case，优先检查 scope 栈状态模型是否统一；尤其 push_scope 不能复用 pop_scope 的 root 保护判断。')
    if _looks_like_routertable(err_text):
        parts.append('优先从 RouterTable 的共享路由契约收口：路径规范化、method 规范化、pattern 编译、resolve 候选优先级、reverse/remove/list_routes 的视图必须共用同一套核心规则。若大量 case 同时报 RouteNotFoundError，不要先补单个特殊路径。')
    if protected:
        parts.append('若失败簇没有明确指向这些区域，请尽量保持不变：' + '、'.join(protected) + '。')
    low_err = (err_text or '').lower()
    if _looks_like_eventbus(err_text) and 'exact' in low_err and 'tail' in low_err and 'single' in low_err and 'global' in low_err and 'task.done' not in low_err and 'stopper' not in low_err and 'late' not in low_err and 'list_subscriptions' not in low_err and 'count("' not in low_err and "count('" not in low_err:
        parts.append('当前失败样例只直接覆盖 emit 的顺序契约；不要在没有直接失败证据时优先修改 once 清理、collect_errors、list_subscriptions(topic) 或 count(topic)。')
    if any(tag.startswith('graph_') for tag in tags):
        parts.append('优先从图契约统一收口：依赖去重、合法性判断、字典序选择、done 快照语义、ready/blocked_count 统计必须在 topo_sort/can_finish/TaskGraph 三组 API 中保持一致。')
    elif 'dispatch_order' in tags or 'stop_semantics' in tags or 'once_semantics' in tags or 'error_collection' in tags:
        parts.append('优先从 emit 主链路统一修复：订阅筛选/排序、handler 调用、called/results/errors 写入、STOP 中断、once 移除、collect_errors 分支必须按同一条主流程处理。')
    if 'list_count' in tags:
        parts.append('list_subscriptions(None) 固定按注册顺序；count(topic) 只统计未 paused 且匹配的订阅。若 dispatch/STOP 与 list 同时失败，先检查 emit 是否应在过滤后保持注册顺序、而 list_subscriptions(topic) 仅承担展示排序，再决定是否真的需要共享排序键。')
    return '\n'.join(parts)


def summarize_lesson_history(lesson_text: str, scene: str) -> str:
    txt = (lesson_text or '').strip()
    if not txt:
        return '[no lessons]'
    if (scene or '').strip().lower() != 'file':
        return txt
    info = parse_lesson_stats(txt)
    parts: list[str] = []
    if info['scores']:
        parts.append('最近通过情况：' + ', '.join(f'{a}/{b}' for a, b in info['scores'][:3]))
    if info['repeated_tags']:
        parts.append('重复失败簇：' + '、'.join(info['repeated_tags']))
    if info['repeated_case_ids']:
        parts.append('重复失败用例：' + '、'.join(f'case#{x}' for x in info['repeated_case_ids'][:6]))
    if info['oscillation'] or info['stagnation']:
        parts.append('检测到修复停滞：最近多轮通过数未提升，避免重复执行相同局部补丁。')
    if info['repeated_strategies']:
        parts.append('重复修复策略：' + ' || '.join(info['repeated_strategies'][:2]))
    if info['strategies']:
        parts.append('最近修复策略摘要：' + ' || '.join(info['strategies'][:3]))
    parts.append('原始 lessons：' + txt[:1200])
    return '\n'.join(parts)
