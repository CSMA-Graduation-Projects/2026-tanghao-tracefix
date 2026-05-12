from __future__ import annotations

import json

from app.core.scene_policy import get_scene_policy
from app.utils.fail_focus import build_case_clue_text
from app.utils.public_api import extract_required_public_names
from app.utils.api_contract import build_case_contract_text


def _scene_rules(scene: str) -> list[str]:
    scene = (scene or 'func').strip().lower()
    if scene == 'class':
        return [
            '你必须生成一个完整的 Python 类文件。',
            '不要退化成只写 solve 函数。',
            '必须保留题目中要求的类名、初始化逻辑、公开方法和内部状态。',
            '方法之间的联动关系必须正确。',
        ]
    if scene == 'file':
        return [
            '你必须生成一个完整的 Python 模块（完整 .py 文件）。',
            '不要退化成只写 solve 函数。',
            '必须保留题目中要求的公开 API，包括函数、类、工具函数和常量。',
            '模块中不同 API 的协作关系必须可运行。',
        ]
    return [
        '你必须生成可以直接被 assert 调用的完整 Python 代码。',
        '默认题目可能要求公开函数 solve，但如果题目里给了其他函数名，必须保持一致。',
        '优先保证边界条件、返回值与题意一致。',
    ]



def _required_public_api_text(problem_text: str, scene: str = 'func', title: str = '') -> str:
    names = extract_required_public_names(problem_text, scene=scene, title=title)
    if not names:
        return ''
    joined = '、'.join(names)
    return (
        '题目中明确要求的公开对象名（必须原样保留并真正定义，不得只在注释或字符串里出现）：\n'
        f'- {joined}\n\n'
    )

def _case_cfg_text(case_cfg: dict | None) -> str:
    cfg = case_cfg or {}
    count = int(cfg.get('count') or 8)
    preset = str(cfg.get('preset') or 'standard')
    focus = str(cfg.get('focus') or 'balanced')
    hint = str(cfg.get('hint') or '').strip()
    return (
        f'- 用例目标数量：{count}\n'
        f'- 用例强度预设：{preset}\n'
        f'- 用例关注重点：{focus}\n'
        + (f'- 用户补充要求：{hint}\n' if hint else '')
    )


def _file_task_addendum(err_text: str, problem_text: str = "", title: str = "") -> str:
    merged = '\n'.join(x for x in [title or '', problem_text or '', err_text or ''] if x)
    low = merged.lower()
    if any(k in low for k in ('topo_sort', 'can_finish', 'taskgraph', 'blocked_count', 'ready(')):
        return (
            '文件级图模块分析/修复补充要求：\n'
            '1. topo_sort、can_finish 与 TaskGraph 三组 API 必须共享同一套图合法性与依赖去重规则。\n'
            '2. 当多个任务同时可执行时，必须按字典序最小优先，不能因为局部状态或重复依赖打乱顺序。\n'
            '3. ready(done) / blocked_count(done) 默认应把 done 视为“本次查询快照”，除非题目明确要求对象维护隐式累积状态。\n'
            '4. 若依赖列表里有重复前置项，同一依赖通常只能算一个真实前置条件，不应在 blocked_count 或 readiness 中被重复计数。\n\n'
        )
    if any(k in low for k in ('routertable', 'routenotfounderror', 'routeconflicterror', 'reversebuilderror', 'list_routes()', 'remove(', '/users/<', '/assets/', '/download/', '/method/test')):
        return (
            '文件级路由模块分析/修复补充要求：\n'
            '1. resolve / reverse / remove / list_routes 必须共享同一套路径规范化与 method 规范化规则；根路径 / 与多斜杠路径要先规范化再参与匹配。\n'
            '2. 参数路由必须同时覆盖 int / str / path 三类片段，并保证 str 只吃单段、path 只在尾段且不能匹配空串。\n'
            '3. resolve 的优先级要统一：priority、静态片段数、参数片段数、注册顺序必须在所有匹配分支上保持一致。\n'
            '4. reverse(handler, method=...)、remove(pattern, methods=...) 与 list_routes() 不能各自维护不同的 pattern/method 视图；method 大小写与去重规则必须一致。\n'
            '5. 若大量失败同时表现为 RouteNotFoundError，优先检查根路径、路径打平/去空段、method 规范化与 pattern 编译，而不是先补单个特殊 case。\n\n'
        )
    if any(k in low for k in ('emit(', 'subscribe(', 'list_subscriptions', 'normalize_topic', 'validate_pattern', 'topic_matches', 'collect_errors', 'stopper')):
        shared_priority = '同一匹配优先级' in merged or 'same matching priority' in low
        list_evidence = any(k in low for k in ('list_subscriptions', 'count(', 'system.boot', 'user.deleted'))
        rule7 = (
            '7. 题目已明确写明 emit 与 list_subscriptions(topic) 使用同一匹配优先级；二者必须复用同一套 priority key。count(topic) 只承担过滤统计，不参与排序。\n'
            if shared_priority else
            ('7. 若当前失败样例已经同时覆盖 emit 与 list_subscriptions(topic)/count，再判断它们是否应共享排序键；若没有直接样例证据，不要先把列表展示逻辑混入 emit 的主因。\n'
             if list_evidence else
             '7. 当前失败样例主要暴露的是 emit/STOP 契约；先把 emit 的权威样例顺序跑通，不要在没有直接证据时把 list_subscriptions(topic)/count 混入同一轮根因。\n')
        )
        return (
            '文件级事件模块分析/修复补充要求：\n'
            '1. 优先总结共同失败簇，而不是只解释第一条失败或单条 trace 噪声。\n'
            '2. 不要仅围绕 normalize_topic/validate_pattern 等已通过区域修改，除非失败簇明确指向这些函数。\n'
            '3. 根因必须尽量同时解释 emit/STOP/once/collect_errors/list_subscriptions/count 等多条失败样例。\n'
            '4. 若稳定失败集中在若干固定 case，必须明确这些 case 共享的公共逻辑，不要继续拆成互不关联的小问题。\n'
            '5. 当题面里的抽象排序描述与多条可执行样例冲突时，优先以可执行样例约束为准；不要为了迎合一段抽象说明而破坏多个已给出的样例。\n'
            '6. 若样例已经明确写出类似 [exact, tail, single, global] 的调用顺序，应把它视为 emit 的权威行为契约：更长的具体前缀 + tail(**) 可以先于更泛的 single(*) / global 模式；不要只按“星号更少/更多”做简单排序。\n'
            '6.1 在输出前请手工 dry-run 一次 user.created 样例，确认 priority key 的真实排序就是 exact > tail > single > global；如果采用数值权重/取负号/升降序排序，请再检查一次没有把 `**` 与 `*` 的先后方向写反。\n'
            f'{rule7}'
            '8. 若 "**" 匹配在复杂 topic 上出现超时，应优先把匹配写成确定性扫描或带记忆化的递归，避免指数级回溯。\n\n'
        )
    if any(k in low for k in ('scopedconfig', 'effective_items', 'itemsr', 'getr', 'render(', 'resolve=true', 'batch_apply', 'push_scope', 'pop_scope', 'freeze_scope', 'unfreeze_scope', 'list_scopes', 'cannot pop root scope', '${host}', '${port}', '$$')):
        return (
            '文件级配置/解析模块分析/修复补充要求：\n'
            '1. render、get(resolve=True) 与 effective_items(resolve=True) 必须共享同一个 resolver；不要分别维护多套 placeholder 解析逻辑。\n'
            '2. resolver 必须保证单调前进、可终止：缺失引用保持原样，$$ 最终还原为单个 $，循环引用抛 ValueError。\n'
            '3. push_scope 与 pop_scope 的守卫语义必须彻底分开：push_scope 只负责校验 scope 名称/重复名并压栈，不能复用“root 不能 pop”的判断；pop_scope 才负责禁止弹出 root。\n'
            '4. freeze_scope / unfreeze_scope / set / delete / list_scopes / pop_scope 必须共享同一套顶部 scope 状态模型；不要让冻结、删除和恢复逻辑各自漂移。\n'
            '5. effective_items(resolve=True) 必须基于“当前最终可见视图”逐 key 解析，而不是线性拼接所有 scope 后再局部覆盖。\n'
            '6. batch_apply 对未知操作、空 tuple、错误 engine 类型这类非法输入，应在追加结果前直接抛异常，不得吞掉后继续返回结果列表。\n'
            '7. 若最近稳定剩余失败只集中在 render/batch_apply，优先收口共享 resolver 的公开语义与批量接口的异常语义，不要继续大改已通过的 scope 栈主逻辑。\n\n'
        )
    return (
        '文件级复杂任务的分析/修复要求：\n'
        '1. 优先修复能同时解释多条失败样例的公共逻辑，不要只为单条断言打补丁。\n'
        '2. 若历史 lesson 显示多轮通过率没有提升，必须明确指出“修复停滞/振荡”，并提出不同于历史的模块级修复方案。\n'
        '3. 稳定失败集中在若干固定 case 时，应优先总结这些 case 共享的模块契约，而不是继续修局部噪声。\n\n'
    )


def build_gen_prompt(problem_text: str, scene: str = 'func', title: str = '', case_texts: list[str] | None = None) -> str:
    rules = '\n'.join(f'{idx + 1}. {item}' for idx, item in enumerate(_scene_rules(scene)))
    public_api_text = _required_public_api_text(problem_text, scene=scene, title=title)
    case_contract_text = build_case_contract_text(problem_text, case_texts, scene=scene, title=title)
    return (
        '你是一名严格的 Python 代码生成助手。\n'
        '请根据题目描述直接返回最终可运行代码。\n'
        '输出要求：\n'
        f'{rules}\n'
        '5. 不要输出解释说明，不要输出 Markdown 标题。\n'
        '6. 可以使用标准库，但不要依赖第三方库。\n'
        '7. 如果测试块已经给出了可执行的构造函数/方法/函数调用方式，必须让代码去适配这些调用，不要假设测试块写错。\n'
        '8. 如果测试块里已经写出了明确断言（返回值、元组结构、字典键、排序结果、优先级、布尔语义），这些断言本身就是行为契约，代码必须直接满足。\n\n'
        f'{public_api_text}'
        f'{case_contract_text}'
        + (f'任务标题：{title}\n\n' if title else '')
        + '题目描述：\n'
        f'{(problem_text or '').strip()}\n'
    )


def build_gen_bundle_prompt(problem_text: str, scene: str = 'func', title: str = '', case_cfg: dict | None = None, case_texts: list[str] | None = None) -> str:
    rules = '\n'.join(f'{idx + 1}. {item}' for idx, item in enumerate(_scene_rules(scene)))
    cfg_text = _case_cfg_text(case_cfg)
    public_api_text = _required_public_api_text(problem_text, scene=scene, title=title)
    case_contract_text = build_case_contract_text(problem_text, case_texts, scene=scene, title=title)
    schema = {
        'code': '完整 Python 代码字符串',
        'cases': [
            {'assert_text': '一条测试用例代码块，可以是单行 assert，也可以是多行准备语句 + assert'}
        ],
    }
    return (
        '你是一名严格的 Python 代码与测试设计助手。\n'
        '现在需要你一次性返回“完整代码 + 高覆盖测试用例”。\n'
        '请只返回一个 JSON 对象，不要输出额外解释。\n\n'
        '代码要求：\n'
        f'{rules}\n'
        '5. 代码必须是完整可运行的最终版本。\n\n'
        '测试用例要求：\n'
        '1. cases 数组里的每一项都必须提供 assert_text。\n'
        '2. assert_text 可以是单行 assert，也可以是多行代码块。\n'
        '3. 测试应尽量覆盖正常输入、边界输入、空输入、重复值、排序稳定性、非法或异常输入（若题意要求）。\n'
        '4. 如果是类文件级任务，请优先让每个测试块自行创建对象并在块内完成完整断言，避免跨块共享对象状态。\n'
        '5. 如果是完整模块级任务，可以包含共享 helper/setup 块，但真正计分的测试块仍应尽量聚焦一个明确行为。\n'
        '6. 测试用例之间尽量相互独立，不要让一个用例依赖前一个用例的运行结果；只有模块级任务在确有必要时才允许显式共享 setup。\n'
        '7. 每个期望值都必须严格依据题意手工推导，不要猜测；若无法确定期望，就不要生成该断言。\n'
        '8. 不要发明题目没有要求的额外契约，不要把“可能更合理”的行为写进断言。\n'
        '9. 如果输入里已经提供了可执行测试块，这些测试调用方式本身也属于代码契约提示；生成的代码必须能适配这些调用。\n'
        f'{public_api_text}'
        f'{case_contract_text}'
        f'{cfg_text}\n'
        'JSON 输出格式示例：\n'
        f'{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n'
        f'任务标题：{title or "未命名任务"}\n'
        '题目描述：\n'
        f'{(problem_text or '').strip()}\n'
    )


def build_case_prompt(problem_text: str, scene: str = 'func', title: str = '', count: int = 8, case_cfg: dict | None = None) -> str:
    merged_cfg = dict(case_cfg or {})
    merged_cfg.setdefault('count', count)
    cfg_text = _case_cfg_text(merged_cfg)
    public_api_text = _required_public_api_text(problem_text, scene=scene, title=title)
    return (
        '你是一名严格的软件测试助手。\n'
        '请根据题目描述，仅返回 JSON 对象，不要输出额外解释。\n'
        'JSON 格式：{"cases": [{"assert_text": "..."}]}\n'
        '要求：\n'
        '1. 生成尽量高覆盖的 assert 测试。\n'
        '2. assert_text 可以是多行代码块。\n'
        '3. 如果题目是类任务，请让每个测试块自带对象创建与方法调用，不要把对象状态隐式留给下一块。\n'
        '4. 如果题目是模块任务，请覆盖多个公开 API 的协作，并且只有在确有必要时才生成共享 helper/setup。\n'
        '5. 不要生成无意义的 assert True。\n'
        '6. 每个期望值都必须严格依据题目描述逐项核算；若不能确认，就不要写这条断言。\n'
        '7. 不要发明题目没有明确要求的额外行为。\n'
        f'{public_api_text}'
        f'{cfg_text}\n'
        f'任务标题：{title or "未命名任务"}\n'
        f'场景：{scene}\n'
        f'题目描述：\n{(problem_text or "").strip()}\n'
    )


def build_case_review_prompt(problem_text: str, scene: str = 'func', title: str = '', cases: list[dict] | None = None) -> str:
    schema = {
        'cases': [
            {'assert_text': '通过审查后保留的一条测试块'}
        ]
    }
    rendered_cases = []
    for idx, item in enumerate(cases or [], start=1):
        rendered_cases.append({
            'idx': idx,
            'assert_text': str((item or {}).get('assert_text') or '').strip(),
        })
    return (
        '你是一名严格的软件测试审查助手。\n'
        '请审查下面这些 AI 生成测试用例是否与题目描述完全一致。\n'
        '如果某条断言的期望值与题目描述冲突、无法从题意严格推出、或引入了题目未要求的额外契约，请删除或改正。\n'
        '请只返回 JSON 对象，不要输出额外解释。\n'
        '返回格式：\n'
        f'{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n'
        f'任务标题：{title or "未命名任务"}\n'
        f'场景：{scene}\n'
        f'题目描述：\n{(problem_text or "").strip()}\n\n'
        '待审查测试用例：\n'
        f'{json.dumps(rendered_cases, ensure_ascii=False, indent=2)}\n'
    )


def build_analysis_prompt(problem_text: str, code_text: str, err_text: str, trace_sum: str = '', lesson_text: str = '', scene: str = 'func', fail_clusters: list[str] | None = None, fail_case_ids: list[int] | None = None, title: str = '', case_texts: list[str] | None = None) -> str:
    pol = get_scene_policy(scene)
    cluster_text = '、'.join(fail_clusters or []) or '暂无'
    case_text = '、'.join(f'case#{x}' for x in (fail_case_ids or [])[:8]) or '暂无'
    case_clue_text = build_case_clue_text(err_text, scene)
    public_api_text = _required_public_api_text(problem_text, scene=scene, title=title)
    case_contract_text = build_case_contract_text(problem_text, case_texts, scene=scene, title=title)
    extra = ''
    if pol.scene == 'file':
        extra = _file_task_addendum(err_text, problem_text=problem_text, title=title)
    elif pol.scene == 'class':
        extra = '类文件级分析要求：优先关注构造函数、对象状态和方法协作，不要退化成单函数修复。\n\n'
    return (
        '你是一名调试分析助手。\n'
        '请根据题目、当前代码、错误信息、轨迹摘要和历史 lesson，输出一个 JSON 对象：\n'
        '{"root_cause": "...", "fix_plan": "...", "inst_sugg": "..."}\n'
        '要求：root_cause 要指出真正错误原因；fix_plan 要给出可执行修复策略；inst_sugg 要指出还应记录什么变量或分支。\n'
        '如果错误信息中同时出现多条失败样例，必须优先总结“共同失败簇”。\n'
        '如果测试块已经明确展示了构造函数/方法/函数的调用方式，则必须把这些调用当作接口真值；禁止在分析结果里建议“修改测试调用方式”。\n'
        '如果测试块里的断言已经明确给出返回结构、元组位置、字典键、排序结果、优先级或布尔语义，也必须把这些断言当作行为契约。\n'
        '如果 trace 中只有单条孤立异常，而大多数失败是 AssertionError，应将该异常视为低置信度噪声。\n'
        f'场景：{pol.label}（{pol.scene}）\n'
        f'场景修复重点：{pol.prompt_focus}\n'
        f'建议轨迹重点：{pol.trace_focus}\n'
        f'主要失败簇：{cluster_text}\n'
        f'稳定失败用例：{case_text}\n'
        f'失败样例线索：\n{case_clue_text or "暂无"}\n\n'
        f'{public_api_text}'
        f'{case_contract_text}'
        f'{extra}'
        + (f'任务标题：{title}\n\n' if title else '')
        + f'题目描述：\n{problem_text.strip()}\n\n'
        f'当前代码：\n{code_text.strip()}\n\n'
        f'错误信息：\n{(err_text or "").strip()}\n\n'
        f'轨迹摘要：\n{(trace_sum or "").strip() or "暂无"}\n\n'
        f'历史 lesson：\n{(lesson_text or "").strip() or "暂无"}\n'
    )


def build_fix_prompt(problem_text: str, code_text: str, err_text: str = '', trace_sum: str = '', lesson_text: str = '', fix_plan: str = '', scene: str = 'func', robust_mode: bool = False, rebuild_mode: bool = False, title: str = '', case_texts: list[str] | None = None) -> str:
    pol = get_scene_policy(scene)
    case_clue_text = build_case_clue_text(err_text, scene)
    public_api_text = _required_public_api_text(problem_text, scene=scene, title=title)
    case_contract_text = build_case_contract_text(problem_text, case_texts, scene=scene, title=title)
    extra = ''
    if pol.scene == 'file':
        extra = _file_task_addendum(err_text, problem_text=problem_text, title=title)
    robust_rules = (
        '稳健性修复要求：\n'
        '1. 禁止为了某个 case、某个示例输入、某个固定字符串或某个 scope/topic 名称写硬编码特判。\n'
        '2. 若多个公开 API 同时失败，必须优先重构共享 helper、共享状态模型或共享排序/过滤契约，而不是分别给每个 API 打补丁。\n'
        '3. 优先保证终止性、一致性、异常语义、返回值语义和跨 API 协作关系。\n'
        '4. 若只有少数稳定剩余 case 还在失败，应先判断这是“共享 helper 的剩余公开语义没收口”还是“批量接口/异常语义没收口”，不要为了旧失败记忆继续大改已经转绿的子路径。\n'
        '5. 若当前代码已经在多个轮次上振荡，请直接按题目契约重写相关核心 helper 或主流程，而不是继续微调单个 if 条件。\n'
        '6. 输出前自检：不要留下半成品 helper、注释占位或缺失 return 的公共函数；所有被多个 API 共享的 helper 必须完整可调用。\n'
        '7. 如果测试块已经直接调用了构造函数/方法/函数，请让代码去适配这些调用；禁止通过“测试应该改成别的调用方式”来规避。\n'
        '8. 如果测试块里的断言已经明确写出返回值、返回结构、排序结果、优先级或布尔语义，必须直接满足这些断言，不得用近似行为替代。\n\n'
    )
    rewrite_hint = ''
    if pol.scene == 'file' and rebuild_mode:
        rewrite_hint = (
            '当前进入“模块级重建优先模式”。\n'
            '不要继续围绕单个 case、单个 if 或单个字符串做补丁；请回到题目契约，先统一重建真正的共享核心。\n'
            '优先目标：公共 resolver / 状态模型 / 过滤与排序主流程 / 批量接口语义的一致性、终止性与异常语义。\n'
            '允许重写内部实现，但必须保持外部 API 名称与题目要求一致；优先保证代码语法正确、可终止、可复用、跨 API 一致。\n\n'
        )
    elif robust_mode and pol.scene == 'file':
        rewrite_hint = (
            '当前进入“模块级稳健重构模式”。\n'
            '请优先从题目契约出发，重写或重构真正的共享核心：公共 resolver / 状态流 / 排序与过滤主流程 / 批量接口语义。\n'
            '你可以保持外部 API 名称不变，但内部实现应以“完整、可终止、可复用、跨 API 一致”为目标。\n\n'
        )
    return (
        '你是一名 Python 代码修复助手。\n'
        '请基于题目、当前代码、错误信息、轨迹摘要、lesson 和修复计划，直接返回修复后的完整代码。\n'
        '不要输出解释说明，只输出最终完整代码。\n\n'
        f'{robust_rules}'
        f'{rewrite_hint}'
        f'{public_api_text}'
        f'{case_contract_text}'
        f'{extra}'
        + (f'任务标题：{title}\n\n' if title else '')
        + f'题目描述：\n{problem_text.strip()}\n\n'
        f'当前代码：\n{code_text.strip()}\n\n'
        f'错误信息：\n{(err_text or "").strip() or "暂无"}\n\n'
        f'失败样例线索：\n{case_clue_text or "暂无"}\n\n'
        f'轨迹摘要：\n{(trace_sum or "").strip() or "暂无"}\n\n'
        f'历史 lesson：\n{(lesson_text or "").strip() or "暂无"}\n\n'
        f'修复计划：\n{(fix_plan or "").strip() or "请直接修复明显错误"}\n'
    )
