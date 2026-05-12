"""内置实验题库（重构版）。

目标：
- 每类题库固定 20 题；
- 不再保留过于简单的入门题；
- 函数级、类级、文件级都提升到中高难度；
- 所有测试块均为可直接执行的 Python 代码块。

说明：
- `custom/mbpp/humaneval` 共用函数级题库；
- `class_bank/class_eval` 共用类级题库；
- `file_bank/file_ultra` 共用文件级题库；
- `sample_cnt` 超过题库大小时会被截断，不循环复用。
"""

from __future__ import annotations

from copy import deepcopy


def _case(assert_text: str, sort_no: int) -> dict:
    return {
        "src_type": "dataset",
        "case_in": None,
        "expect_out": None,
        "assert_text": assert_text,
        "weight": 1.0,
        "sort_no": sort_no,
    }


def _block(lines: list[str], sort_no: int) -> dict:
    return _case("\n".join(lines), sort_no)


_FUNC_POOL = [
    {
        "title": "区间合并与规范化",
        "scene": "func",
        "problem_text": "请实现 solve(intervals)，输入若干闭区间 [l, r]，先按起点升序、终点升序规范化，再合并所有重叠或相邻区间，返回合并后的区间列表。",
        "cases": [
            _case("assert solve([[1,3],[2,4],[6,8],[8,10]]) == [[1,4],[6,10]]", 1),
            _case("assert solve([[5,5],[1,2],[3,4]]) == [[1,5]]", 2),
        ],
    },
    {
        "title": "Unix 路径规范化",
        "scene": "func",
        "problem_text": "请实现 solve(path)，按 Unix 规则规范化路径：处理重复斜杠、.、..，最终返回绝对路径字符串。",
        "cases": [
            _case("assert solve('/a//b/./c/../d') == '/a/b/d'", 1),
            _case("assert solve('/../../x/y') == '/x/y'", 2),
        ],
    },
    {
        "title": "RPN 表达式求值",
        "scene": "func",
        "problem_text": "请实现 solve(tokens)，计算逆波兰表达式。运算符仅包含 + - * /，其中除法按向零截断。",
        "cases": [
            _case("assert solve(['2','1','+','3','*']) == 9", 1),
            _case("assert solve(['4','13','5','/','+']) == 6", 2),
            _case("assert solve(['10','6','9','3','+','-11','*','/','*','17','+','5','+']) == 22", 3),
        ],
    },
    {
        "title": "括号字符串解码",
        "scene": "func",
        "problem_text": "请实现 solve(s)，解码形如 k[encoded] 的嵌套重复字符串，k 为正整数。",
        "cases": [
            _case("assert solve('3[a2[c]]') == 'accaccacc'", 1),
            _case("assert solve('2[ab]3[c]') == 'ababccc'", 2),
        ],
    },
    {
        "title": "最长有效括号长度",
        "scene": "func",
        "problem_text": "请实现 solve(s)，返回括号串中最长有效（格式正确且连续）的子串长度。",
        "cases": [
            _case("assert solve(')()())') == 4", 1),
            _case("assert solve('(()') == 2", 2),
            _case("assert solve('()(())') == 6", 3),
        ],
    },
    {
        "title": "最小覆盖子串",
        "scene": "func",
        "problem_text": "请实现 solve(s, t)，返回 s 中最短的一个子串，使其覆盖 t 中全部字符及出现次数；若不存在则返回空串。",
        "cases": [
            _case("assert solve('ADOBECODEBANC', 'ABC') == 'BANC'", 1),
            _case("assert solve('a', 'aa') == ''", 2),
        ],
    },
    {
        "title": "插入并合并区间",
        "scene": "func",
        "problem_text": "请实现 solve(intervals, new_interval)，其中 intervals 已按起点升序且互不重叠；插入 new_interval 后返回新的有序合并结果。",
        "cases": [
            _case("assert solve([[1,3],[6,9]], [2,5]) == [[1,5],[6,9]]", 1),
            _case("assert solve([[1,2],[3,5],[6,7],[8,10],[12,16]], [4,8]) == [[1,2],[3,10],[12,16]]", 2),
        ],
    },
    {
        "title": "除自身以外数组乘积",
        "scene": "func",
        "problem_text": "请实现 solve(nums)，返回数组，其中每个位置是除自身外其余元素的乘积；不能使用除法。",
        "cases": [
            _case("assert solve([1,2,3,4]) == [24,12,8,6]", 1),
            _case("assert solve([-1,1,0,-3,3]) == [0,0,9,0,0]", 2),
        ],
    },
    {
        "title": "接雨水",
        "scene": "func",
        "problem_text": "请实现 solve(height)，给定柱状图高度，返回下雨后能够接住的水量。",
        "cases": [
            _case("assert solve([0,1,0,2,1,0,1,3,2,1,2,1]) == 6", 1),
            _case("assert solve([4,2,0,3,2,5]) == 9", 2),
        ],
    },
    {
        "title": "按首次出现顺序分组异位词",
        "scene": "func",
        "problem_text": "请实现 solve(words)，将异位词分组；组内保持原出现顺序，组与组之间按首个成员首次出现顺序排列。",
        "cases": [
            _case("assert solve(['eat','tea','tan','ate','nat','bat']) == [['eat','tea','ate'],['tan','nat'],['bat']]", 1),
            _case("assert solve(['ab','ba','abc','cba','bca']) == [['ab','ba'],['abc','cba','bca']]", 2),
        ],
    },
    {
        "title": "稳定 TopK 高频元素",
        "scene": "func",
        "problem_text": "请实现 solve(nums, k)，返回前 k 个高频元素；频率相同则按首次出现位置更早者优先。",
        "cases": [
            _case("assert solve([1,1,2,2,3,3,3,4], 2) == [3,1]", 1),
            _case("assert solve([5,6,5,7,6,8], 2) == [5,6]", 2),
        ],
    },
    {
        "title": "螺旋读取矩阵",
        "scene": "func",
        "problem_text": "请实现 solve(matrix)，按顺时针螺旋顺序读取矩阵并返回结果列表。",
        "cases": [
            _case("assert solve([[1,2,3],[4,5,6],[7,8,9]]) == [1,2,3,6,9,8,7,4,5]", 1),
            _case("assert solve([[1,2,3,4],[5,6,7,8],[9,10,11,12]]) == [1,2,3,4,8,12,11,10,9,5,6,7]", 2),
        ],
    },
    {
        "title": "滑动窗口最大值",
        "scene": "func",
        "problem_text": "请实现 solve(nums, k)，返回长度为 k 的每个滑动窗口中的最大值列表。",
        "cases": [
            _case("assert solve([1,3,-1,-3,5,3,6,7], 3) == [3,3,5,5,6,7]", 1),
            _case("assert solve([9,8,7,6,5], 2) == [9,8,7,6]", 2),
        ],
    },
    {
        "title": "字符串分区标签",
        "scene": "func",
        "problem_text": "请实现 solve(s)，将字符串划分为尽可能多的片段，使每个字母最多出现在一个片段中，返回各片段长度。",
        "cases": [
            _case("assert solve('ababcbacadefegdehijhklij') == [9,7,8]", 1),
            _case("assert solve('eccbbbbdec') == [10]", 2),
        ],
    },
    {
        "title": "网格最短路径（含障碍）",
        "scene": "func",
        "problem_text": "请实现 solve(grid)，0 表示可走，1 表示障碍，从左上到右下只允许四连通移动，返回最短路径长度；若不可达返回 -1。起点终点都计步数 1。",
        "cases": [
            _case("assert solve([[0,0,0],[1,1,0],[0,0,0]]) == 5", 1),
            _case("assert solve([[0,1],[1,0]]) == -1", 2),
        ],
    },
    {
        "title": "岛屿数量",
        "scene": "func",
        "problem_text": "请实现 solve(grid)，给定由 '1' 和 '0' 组成的网格，返回岛屿数量。",
        "cases": [
            _case("assert solve([['1','1','0'],['0','1','0'],['1','0','1']]) == 3", 1),
            _case("assert solve([['1','1','1'],['0','1','0'],['1','1','1']]) == 1", 2),
        ],
    },
    {
        "title": "单词网格搜索",
        "scene": "func",
        "problem_text": "请实现 solve(board, word)，判断 word 是否可在二维字符网格中通过上下左右相邻单元拼出，且同一单元不能重复使用。",
        "cases": [
            _case("assert solve([['A','B','C','E'],['S','F','C','S'],['A','D','E','E']], 'ABCCED') is True", 1),
            _case("assert solve([['A','B'],['C','D']], 'ABCD') is False", 2),
        ],
    },
    {
        "title": "最少会议室数",
        "scene": "func",
        "problem_text": "请实现 solve(intervals)，intervals 表示会议开始结束时间 [s, e)，返回安排所有会议所需的最少会议室数量。",
        "cases": [
            _case("assert solve([[0,30],[5,10],[15,20]]) == 2", 1),
            _case("assert solve([[7,10],[2,4]]) == 1", 2),
        ],
    },
    {
        "title": "矩阵零扩散",
        "scene": "func",
        "problem_text": "请实现 solve(matrix)，若矩阵某元素为 0，则其所在整行整列都应变为 0；返回变换后的新矩阵。",
        "cases": [
            _case("assert solve([[1,1,1],[1,0,1],[1,1,1]]) == [[1,0,1],[0,0,0],[1,0,1]]", 1),
            _case("assert solve([[0,1,2],[3,4,5],[6,7,0]]) == [[0,0,0],[0,4,0],[0,0,0]]", 2),
        ],
    },
    {
        "title": "最接近目标和的三数和",
        "scene": "func",
        "problem_text": "请实现 solve(nums, target)，返回三个数之和中最接近 target 的值；若差值相同，返回较小的和。",
        "cases": [
            _case("assert solve([-1,2,1,-4], 1) == 2", 1),
            _case("assert solve([0,0,0], 1) == 0", 2),
        ],
    },

]


_CLASS_POOL = [
    {
        "title": "RunningMedian 数据流中位数",
        "scene": "class",
        "problem_text": "请实现类 RunningMedian，支持 add(num) 与 median()；当元素个数为偶数时，median 返回两个中间数的平均值。",
        "cases": [
            _block(["rm = RunningMedian()", "for x in [5,2,8,3]: rm.add(x)", "assert rm.median() == 4.0"], 1),
            _block(["rm = RunningMedian()", "for x in [1,2,3]: rm.add(x)", "assert rm.median() == 2"], 2),
        ],
    },
    {
        "title": "WindowCounter 滑动计数器",
        "scene": "class",
        "problem_text": "请实现类 WindowCounter(window_size)，支持 hit(ts) 和 count(ts)。count(ts) 返回 [ts-window_size+1, ts] 范围内累计 hit 次数。时间戳非严格连续但单调不减。",
        "cases": [
            _block(["wc = WindowCounter(5)", "for t in [1,2,2,6,7]: wc.hit(t)", "assert wc.count(7) == 3"], 1),
            _block(["wc = WindowCounter(3)", "for t in [10,11,13]: wc.hit(t)", "assert wc.count(13) == 2"], 2),
        ],
    },
    {
        "title": "VersionCounter 带版本回溯计数器",
        "scene": "class",
        "problem_text": "请实现类 VersionCounter，支持 inc(key, delta=1)、snapshot() 返回版本号、get(key, version=None) 读取某 key 在指定版本或最新版本的值。未出现的 key 视为 0。",
        "cases": [
            _block(["vc = VersionCounter()", "vc.inc('a', 2)", "v1 = vc.snapshot()", "vc.inc('a', 3)", "assert vc.get('a') == 5", "assert vc.get('a', v1) == 2"], 1),
            _block(["vc = VersionCounter()", "v0 = vc.snapshot()", "assert vc.get('x', v0) == 0"], 2),
        ],
    },
    {
        "title": "BookingCalendar 不重叠日程表",
        "scene": "class",
        "problem_text": "请实现类 BookingCalendar，支持 book(start, end)。区间采用 [start, end)；若与已有区间重叠返回 False，否则插入并返回 True。",
        "cases": [
            _block(["bc = BookingCalendar()", "assert bc.book(10, 20) is True", "assert bc.book(15, 25) is False", "assert bc.book(20, 30) is True"], 1),
            _block(["bc = BookingCalendar()", "assert bc.book(1, 2) is True", "assert bc.book(2, 3) is True"], 2),
        ],
    },
    {
        "title": "UndoStringBuilder 可撤销字符串构造器",
        "scene": "class",
        "problem_text": "请实现类 UndoStringBuilder，支持 append(s)、delete(k)、undo()、text()。delete(k) 删除末尾 k 个字符；undo 撤销最近一次 append/delete。",
        "cases": [
            _block(["sb = UndoStringBuilder()", "sb.append('abc')", "sb.append('xyz')", "sb.delete(2)", "assert sb.text() == 'abcx'", "sb.undo()", "assert sb.text() == 'abcxyz'"], 1),
            _block(["sb = UndoStringBuilder()", "sb.append('hi')", "sb.delete(5)", "assert sb.text() == ''", "sb.undo()", "assert sb.text() == 'hi'"], 2),
        ],
    },
    {
        "title": "TopKTracker 实时前 K 名",
        "scene": "class",
        "problem_text": "请实现类 TopKTracker(k)，支持 add(key, score_delta) 与 topk()。按总分降序返回前 k 项；分数相同按 key 字典序升序。",
        "cases": [
            _block(["tk = TopKTracker(2)", "tk.add('alice', 5)", "tk.add('bob', 7)", "tk.add('alice', 4)", "tk.add('cara', 9)", "assert tk.topk() == [('alice', 9), ('cara', 9)]"], 1),
            _block(["tk = TopKTracker(3)", "tk.add('x', 1)", "assert tk.topk() == [('x', 1)]"], 2),
        ],
    },
    {
        "title": "FreqStack 最高频弹栈",
        "scene": "class",
        "problem_text": "请实现类 FreqStack，支持 push(x) 和 pop()；pop 返回当前频率最高且最近压入的元素。",
        "cases": [
            _block(["fs = FreqStack()", "for x in [5,7,5,7,4,5]: fs.push(x)", "assert [fs.pop(), fs.pop(), fs.pop(), fs.pop()] == [5,7,5,4]"], 1),
        ],
    },
    {
        "title": "RateLimiter 固定窗口限流",
        "scene": "class",
        "problem_text": "请实现类 RateLimiter(limit, window_size)，支持 allow(ts, key)。同一 key 在任意长度为 window_size 的时间窗口内最多允许 limit 次。时间戳单调不减。",
        "cases": [
            _block(["rl = RateLimiter(2, 5)", "assert rl.allow(1, 'u') is True", "assert rl.allow(2, 'u') is True", "assert rl.allow(3, 'u') is False", "assert rl.allow(7, 'u') is True"], 1),
            _block(["rl = RateLimiter(1, 3)", "assert rl.allow(1, 'a') is True", "assert rl.allow(2, 'b') is True", "assert rl.allow(2, 'a') is False"], 2),
        ],
    },
    {
        "title": "PrefixMap 前缀映射",
        "scene": "class",
        "problem_text": "请实现类 PrefixMap，支持 set(key, value)、get(key)、sum(prefix) 返回所有以 prefix 开头 key 的 value 之和。后续 set 会覆盖旧值。",
        "cases": [
            _block(["pm = PrefixMap()", "pm.set('apple', 3)", "assert pm.sum('ap') == 3", "pm.set('app', 2)", "assert pm.sum('ap') == 5", "pm.set('apple', 2)", "assert pm.sum('ap') == 4"], 1),
        ],
    },
    {
        "title": "IntervalSet 区间集合",
        "scene": "class",
        "problem_text": "请实现类 IntervalSet，支持 add(l, r) 插入闭区间并自动合并；contains(x) 判断点是否落在任一区间；intervals() 返回合并后的升序区间。",
        "cases": [
            _block(["s = IntervalSet()", "s.add(1, 3)", "s.add(5, 7)", "s.add(2, 6)", "assert s.intervals() == [[1, 7]]", "assert s.contains(4) is True", "assert s.contains(8) is False"], 1),
        ],
    },
    {
        "title": "TokenBucket 令牌桶",
        "scene": "class",
        "problem_text": "请实现类 TokenBucket(capacity, refill_per_sec)，支持 allow(ts, cost=1)。按时间流逝补充令牌，最多不超过容量。",
        "cases": [
            _block(["tb = TokenBucket(5, 1)", "assert tb.allow(0, 3) is True", "assert tb.allow(0, 3) is False", "assert tb.allow(2, 2) is True", "assert tb.allow(6, 4) is True"], 1),
        ],
    },
    {
        "title": "TaskJournal 可回滚任务日志",
        "scene": "class",
        "problem_text": "请实现类 TaskJournal，支持 add(task, status)、latest(task)、rollback(task) 回滚到该任务上一条状态并返回当前状态；若无历史则返回 None。",
        "cases": [
            _block(["tj = TaskJournal()", "tj.add('A', 'todo')", "tj.add('A', 'doing')", "tj.add('A', 'done')", "assert tj.latest('A') == 'done'", "assert tj.rollback('A') == 'doing'", "assert tj.latest('A') == 'doing'"], 1),
        ],
    },
    {
        "title": "StackMachine 迷你栈虚拟机",
        "scene": "class",
        "problem_text": "请实现类 StackMachine，支持 exec(program) 执行指令列表。支持 PUSH x, ADD, SUB, MUL, DUP, POP；返回最终栈。",
        "cases": [
            _block(["sm = StackMachine()", "assert sm.exec(['PUSH 2','PUSH 3','ADD','DUP','PUSH 4','MUL']) == [5,20]"], 1),
            _block(["sm = StackMachine()", "assert sm.exec(['PUSH 9','PUSH 4','SUB']) == [5]"], 2),
        ],
    },
    {
        "title": "TrieCounter 词频前缀树",
        "scene": "class",
        "problem_text": "请实现类 TrieCounter，支持 add(word)、count(word)、prefix_count(prefix)。",
        "cases": [
            _block(["tc = TrieCounter()", "for w in ['app','apple','app','apt']: tc.add(w)", "assert tc.count('app') == 2", "assert tc.prefix_count('ap') == 4", "assert tc.prefix_count('app') == 3"], 1),
        ],
    },
    {
        "title": "SeatManager 最小空位分配",
        "scene": "class",
        "problem_text": "请实现类 SeatManager(n)，支持 reserve() 返回当前最小可用座位号，unreserve(x) 释放座位。",
        "cases": [
            _block(["sm = SeatManager(5)", "assert [sm.reserve(), sm.reserve()] == [1,2]", "sm.unreserve(1)", "assert [sm.reserve(), sm.reserve()] == [1,3]"], 1),
        ],
    },
    {
        "title": "SparseVector 稀疏向量",
        "scene": "class",
        "problem_text": "请实现类 SparseVector(nums)，支持 dot(other) 计算点积。",
        "cases": [
            _block(["v1 = SparseVector([1,0,0,2,3])", "v2 = SparseVector([0,3,0,4,0])", "assert v1.dot(v2) == 8"], 1),
            _block(["v1 = SparseVector([0,1,0,0,2,0,0])", "v2 = SparseVector([1,0,0,0,3,0,4])", "assert v1.dot(v2) == 6"], 2),
        ],
    },
    {
        "title": "UnionFindLite 并查集",
        "scene": "class",
        "problem_text": "请实现类 UnionFindLite(n)，支持 union(a,b)、connected(a,b)、group_count()。",
        "cases": [
            _block(["uf = UnionFindLite(5)", "uf.union(0,1)", "uf.union(1,2)", "assert uf.connected(0,2) is True", "assert uf.connected(3,4) is False", "assert uf.group_count() == 3"], 1),
        ],
    },
    {
        "title": "WeightedRandomBag 带权抽样模拟器（确定性）",
        "scene": "class",
        "problem_text": "请实现类 WeightedRandomBag，支持 add(key, weight) 与 pick(x)，其中 x 是 [0, total_weight) 内的整数，按累计权重确定返回哪个 key，因此 pick 是确定性的。",
        "cases": [
            _block(["bag = WeightedRandomBag()", "bag.add('a', 2)", "bag.add('b', 3)", "bag.add('c', 1)", "assert [bag.pick(0), bag.pick(2), bag.pick(5)] == ['a','b','c']"], 1),
        ],
    },
    {
        "title": "RankedQueue 按优先级与时间出队",
        "scene": "class",
        "problem_text": "请实现类 RankedQueue，支持 push(item, priority)、pop()。优先级高者先出；同优先级按更早入队先出。",
        "cases": [
            _block(["rq = RankedQueue()", "rq.push('a', 1)", "rq.push('b', 3)", "rq.push('c', 3)", "rq.push('d', 2)", "assert [rq.pop(), rq.pop(), rq.pop(), rq.pop()] == ['b','c','d','a']"], 1),
        ],
    },
    {
        "title": "GraphPathCounter 有向无环图路径数",
        "scene": "class",
        "problem_text": "请实现类 GraphPathCounter(n, edges)，支持 count_paths(src, dst) 计算 DAG 中从 src 到 dst 的不同路径条数。",
        "cases": [
            _block(["g = GraphPathCounter(5, [(0,1),(0,2),(1,3),(2,3),(3,4)])", "assert g.count_paths(0, 4) == 2", "assert g.count_paths(1, 4) == 1"], 1),
        ],
    },
]


_FILE_POOL = [
    {
        "title": "ScopedConfig 分层变量配置引擎模块",
        "scene": "file",
        "problem_text": "请实现一个完整 Python 模块，核心类名为 ScopedConfig，支持 key 规范化、placeholder 提取、多层 scope、render/get(resolve=True)、effective_items 与 batch_apply。要求统一 resolver、支持 $$ 字面量、缺失引用保持原样、循环引用抛 ValueError。",
        "cases": [
            _block(["cfg = ScopedConfig({'host': 'localhost', 'port': '8080'})", "assert cfg.render('http://${host}:${port}') == 'http://localhost:8080'", "assert cfg.render('money=$$100') == 'money=$100'"], 1),
            _block(["cfg = ScopedConfig({'a': '${b}', 'b': 'B'})", "cfg.set('c', 'X-${a}')", "assert cfg.get('a', resolve=True) == 'B'", "assert cfg.get('c', resolve=True) == 'X-B'"], 2),
            _block(["cfg = ScopedConfig({'a': '${b}', 'b': '${a}'})", "ok = False", "try:", "    cfg.render('v=${a}')", "except ValueError:", "    ok = True", "assert ok is True"], 3),
        ],
    },
    {
        "title": "VersionedKV 版本化键值存储模块",
        "scene": "file",
        "problem_text": "请实现完整模块，提供 normalize_key、VersionedKV、batch_apply。要求 key 大小写与空白统一、每个 key 保存多个版本、支持 history/delete 和批量操作。",
        "cases": [
            _block(["kv = VersionedKV()", "assert kv.set(' Foo ', 10) == 1", "assert kv.set('foo', 20) == 2", "assert kv.get('FOO') == 20", "assert kv.get('foo', 1) == 10"], 1),
            _block(["kv = VersionedKV()", "kv.set('a', 1)", "kv.set('a', 2)", "assert kv.history('A') == [1, 2]", "assert kv.delete('a') is True", "assert kv.delete('a') is False"], 2),
        ],
    },
    {
        "title": "TaskGraph 任务依赖图模块",
        "scene": "file",
        "problem_text": "请实现完整模块，提供 topo_sort、can_finish 和 TaskGraph。要求统一缺失依赖/环检测、ready(done) 与 blocked_count(done) 使用查询快照语义，重复依赖只算一个前置条件。",
        "cases": [
            _block(["assert topo_sort({'a': [], 'b': ['a'], 'c': ['a']}) == ['a', 'b', 'c']", "assert can_finish({'a': [], 'b': ['a']}) is True"], 1),
            _block(["g = TaskGraph({'a': [], 'b': ['a', 'a'], 'c': ['b']})", "assert g.ready([]) == ['a']", "assert g.blocked_count([]) == 2", "assert g.ready(['a']) == ['b']"], 2),
        ],
    },
    {
        "title": "EventBus 通配主题事件总线模块",
        "scene": "file",
        "problem_text": "请实现完整模块，核心类 EventBus。要求支持 topic 规范化、* / ** 通配、subscribe / emit / once / STOP / collect_errors / list_subscriptions / count。emit 与 list_subscriptions(topic) 使用同一匹配优先级，count 只做过滤统计。",
        "cases": [
            _block(["bus = EventBus()", "called = []", "bus.subscribe('user.created', lambda *_: called.append('exact'))", "bus.subscribe('user.*', lambda *_: called.append('single'))", "bus.subscribe('user.**', lambda *_: called.append('tail'))", "bus.subscribe('*.*', lambda *_: called.append('global'))", "bus.emit('user.created')", "assert called == ['exact', 'tail', 'single', 'global']"], 1),
            _block(["bus = EventBus()", "seen = []", "def late(*_): seen.append('late')", "def stopper(*_): seen.append('stopper'); return STOP", "bus.subscribe('task.done', late)", "bus.subscribe('task.**', stopper)", "assert bus.emit('task.done') is STOP", "assert seen == ['late', 'stopper']"], 2),
        ],
    },
    {
        "title": "OverlayRouter 分层路径路由规则模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 add_rule/remove_rule/resolve/list_rules/build，多 scope 叠加，匹配规则含静态段、{name}、*、**，resolve 与 list_rules(path) 必须共享同一优先级。",
        "cases": [
            _block(["rt = OverlayRouter()", "rt.add_rule('root', 'GET', '/users/{id}', 'user-detail')", "rt.add_rule('root', 'GET', '/users/*/posts', 'user-posts')", "assert rt.resolve('GET', '/users/42') == ('user-detail', {'id': '42'}, 'root')"], 1),
            _block(["rt = OverlayRouter()", "rt.add_rule('root', 'GET', '/a/**', 'tail')", "rt.add_rule('root', 'GET', '/a/b', 'exact')", "assert [x[2] for x in rt.list_rules('GET', '/a/b')] == ['exact', 'tail']"], 2),
        ],
    },
    {
        "title": "PathPolicy 多作用域路径策略引擎模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持规则匹配、* / ** 通配、多作用域覆盖、SKIP 继续匹配、disabled 开关、trace 输出与 batch_apply。",
        "cases": [
            _block(["pp = PathPolicy()", "pp.push_scope('root')", "pp.add_rule('GET', '/docs/**', 'allow', 'docs')", "assert pp.decide('GET', '/docs/a/b')['decision'] == 'allow'"], 1),
            _block(["pp = PathPolicy()", "pp.push_scope('root')", "pp.add_rule('*', '/admin/**', 'deny', 'admin')", "pp.push_scope('debug')", "pp.add_rule('GET', '/admin/ping', 'allow', 'ping')", "assert pp.decide('GET', '/admin/ping')['rule_name'] == 'ping'"], 2),
        ],
    },
    {
        "title": "TemplateEnv 模板环境解析模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 register, render, find_placeholders, include, 循环 include 检测，以及严格/宽松两种缺失变量模式。",
        "cases": [
            _block(["env = TemplateEnv()", "env.register('base', 'hi ${name}')", "assert env.render('base', {'name': 'Tom'}) == 'hi Tom'"], 1),
            _block(["env = TemplateEnv()", "env.register('a', 'A {% include b %}')", "env.register('b', 'B')", "assert env.render('a', {}) == 'A B'"], 2),
        ],
    },
    {
        "title": "RuleTable 规则表决策模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 add_rule/evaluate/explain/batch_apply。规则具备 priority、条件集合和 stop_on_match。evaluate 返回命中的规则名与动作。",
        "cases": [
            _block(["rt = RuleTable()", "rt.add_rule('vip', {'level': 'vip'}, 'discount', priority=10)", "rt.add_rule('new', {'is_new': True}, 'gift', priority=5)", "assert rt.evaluate({'level': 'vip', 'is_new': True})[0] == 'discount'"], 1),
        ],
    },
    {
        "title": "RangeMap 区间映射模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 put(l,r,val)、remove(l,r)、get(x)、items()。区间为半开区间 [l,r)，重叠写入应拆分并覆盖。",
        "cases": [
            _block(["rm = RangeMap()", "rm.put(0, 5, 'A')", "rm.put(2, 4, 'B')", "assert rm.get(1) == 'A'", "assert rm.get(3) == 'B'", "assert rm.items() == [(0, 2, 'A'), (2, 4, 'B'), (4, 5, 'A')]"], 1),
        ],
    },
    {
        "title": "PermissionMatrix 权限矩阵模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 grant/revoke/check/list_effective，多 role 叠加，deny 优先级高于 allow。",
        "cases": [
            _block(["pm = PermissionMatrix()", "pm.grant('admin', 'read', 'allow')", "pm.grant('guest', 'read', 'deny')", "assert pm.check(['admin'], 'read') == 'allow'", "assert pm.check(['admin','guest'], 'read') == 'deny'"], 1),
        ],
    },
    {
        "title": "PackageResolver 包依赖解析模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 add_pkg, install_order, can_install, blocked_by。要求统一缺失依赖/环检测，并按字典序生成安装序列。",
        "cases": [
            _block(["pr = PackageResolver()", "pr.add_pkg('c', [])", "pr.add_pkg('b', ['c'])", "pr.add_pkg('a', ['b'])", "assert pr.install_order() == ['c', 'b', 'a']", "assert pr.can_install() is True"], 1),
        ],
    },
    {
        "title": "LedgerBook 记账本模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 post, balance, statement, transfer。要求双分录一致、余额累计正确，transfer 必须原子化写入两条记录。",
        "cases": [
            _block(["lb = LedgerBook()", "lb.post('cash', 100)", "lb.transfer('cash', 'bank', 40)", "assert lb.balance('cash') == 60", "assert lb.balance('bank') == 40"], 1),
        ],
    },
    {
        "title": "ACLMatcher 访问控制匹配模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 CIDR/单 IP/用户名规则匹配，优先级为更具体规则优先，再按 priority，再按注册顺序。",
        "cases": [
            _block(["acl = ACLMatcher()", "acl.add_rule('10.0.0.0/8', 'deny', 'net')", "acl.add_rule('10.1.1.1', 'allow', 'host')", "assert acl.check('10.1.1.1') == ('allow', 'host')"], 1),
        ],
    },
    {
        "title": "WorkflowEngine 工作流状态机模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 define_state, add_transition, can_fire, fire, history。要求状态定义、合法迁移、历史记录一致。",
        "cases": [
            _block(["wf = WorkflowEngine('draft')", "wf.add_transition('draft', 'submit', 'review')", "wf.add_transition('review', 'approve', 'done')", "assert wf.fire('submit') == 'review'", "assert wf.fire('approve') == 'done'", "assert wf.history() == ['draft', 'review', 'done']"], 1),
        ],
    },
    {
        "title": "AliasRegistry 别名注册模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 add_alias、resolve、reverse_refs、detect_cycle。别名链最终应解析到真实目标，循环引用抛 ValueError。",
        "cases": [
            _block(["ar = AliasRegistry()", "ar.add_alias('prod', 'cluster-a')", "ar.add_alias('live', 'prod')", "assert ar.resolve('live') == 'cluster-a'", "assert ar.reverse_refs('cluster-a') == ['live', 'prod']"], 1),
            _block(["ar = AliasRegistry()", "ar.add_alias('a', 'b')", "ar.add_alias('b', 'a')", "ok = False", "try:", "    ar.resolve('a')", "except ValueError:", "    ok = True", "assert ok is True"], 2),
        ],
    },
    {
        "title": "InventoryLedger 库存流水模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 inbound, outbound, stock, history, rollback_last。出库不足应抛 ValueError。",
        "cases": [
            _block(["inv = InventoryLedger()", "inv.inbound('sku1', 10)", "inv.outbound('sku1', 3)", "assert inv.stock('sku1') == 7", "assert len(inv.history('sku1')) == 2"], 1),
        ],
    },
    {
        "title": "GraphQuery 图查询模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 add_edge, bfs_path, topo_sort, connected_components。无向查询与有向拓扑逻辑应各自独立但共享底层存储。",
        "cases": [
            _block(["g = GraphQuery()", "g.add_edge('a', 'b')", "g.add_edge('b', 'c')", "assert g.bfs_path('a', 'c') == ['a', 'b', 'c']"], 1),
            _block(["g = GraphQuery(directed=True)", "g.add_edge('a', 'b')", "g.add_edge('b', 'c')", "assert g.topo_sort() == ['a', 'b', 'c']"], 2),
        ],
    },
    {
        "title": "MiniSQL 内存查询模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 create_table, insert, select(where=None, order_by=None), update。where 由字段到值的精确匹配组成。",
        "cases": [
            _block(["db = MiniSQL()", "db.create_table('user', ['id', 'name'])", "db.insert('user', {'id': 2, 'name': 'B'})", "db.insert('user', {'id': 1, 'name': 'A'})", "assert db.select('user', order_by='id') == [{'id': 1, 'name': 'A'}, {'id': 2, 'name': 'B'}]"], 1),
        ],
    },
    {
        "title": "JobQueue 优先级作业队列模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 push, ack, requeue, next_job, stats。next_job 返回优先级最高、最早入队且未确认的作业。",
        "cases": [
            _block(["jq = JobQueue()", "a = jq.push('a', 1)", "b = jq.push('b', 3)", "assert jq.next_job()['job_id'] == b", "jq.ack(b)", "assert jq.next_job()['job_id'] == a"], 1),
        ],
    },
    {
        "title": "TableJoiner 表连接模块",
        "scene": "file",
        "problem_text": "请实现完整模块，支持 inner_join/left_join，输入为字典列表，按指定键连接。相同键多行匹配需要笛卡尔展开。",
        "cases": [
            _block(["left = [{'id': 1, 'x': 'A'}, {'id': 2, 'x': 'B'}]", "right = [{'id': 1, 'y': 10}, {'id': 1, 'y': 20}]", "tj = TableJoiner()", "assert tj.inner_join(left, right, 'id') == [{'id': 1, 'x': 'A', 'y': 10}, {'id': 1, 'x': 'A', 'y': 20}]"], 1),
        ],
    },
]


_DATASET_ALIAS = {
    'custom': _FUNC_POOL,
    'mbpp': _FUNC_POOL,
    'humaneval': _FUNC_POOL,
    'class_bank': _CLASS_POOL,
    'class_eval': _CLASS_POOL,
    'file_bank': _FILE_POOL,
    'file_ultra': _FILE_POOL,
}

# 实验创建界面只展示“去重后的主数据集”；旧别名仍然保留兼容，
# 以便历史实验记录、旧前端缓存或外部接口参数继续可用。
_DATASET_CANONICAL = {
    'custom': {
        'display_name': '函数级题库',
        'desc': '函数级中高难题库，覆盖窗口、区间、图、字符串解析与动态规划等问题。',
        'aliases': ['mbpp', 'humaneval'],
    },
    'class_bank': {
        'display_name': '类文件级题库',
        'desc': '类级中高难题库，强调对象状态、历史版本、优先级、滑动窗口与图结构协作。',
        'aliases': ['class_eval'],
    },
    'file_bank': {
        'display_name': '文件级题库',
        'desc': '文件级高难题库：完整模块、多公开 API、共享 helper、复杂契约、异常语义与排序/状态一致性。',
        'aliases': ['file_ultra'],
    },
}


def _canonical_dataset_name(name: str | None) -> str:
    raw = str(name or 'custom').strip() or 'custom'
    if raw in _DATASET_CANONICAL:
        return raw
    for canonical, meta in _DATASET_CANONICAL.items():
        if raw in meta.get('aliases', []):
            return canonical
    return 'custom'



def get_dataset_names() -> list[str]:
    return list(_DATASET_CANONICAL.keys())



def get_dataset_size(name: str) -> int:
    pool = _DATASET_ALIAS.get(name or 'custom', _FUNC_POOL)
    return len(pool)



def get_dataset_meta(name: str) -> dict:
    canonical = _canonical_dataset_name(name)
    meta = _DATASET_CANONICAL[canonical]
    return {
        'name': canonical,
        'display_name': meta['display_name'],
        'desc': meta['desc'],
        'size': get_dataset_size(canonical),
        'aliases': list(meta.get('aliases', [])),
        'input_name': str(name or canonical),
        'alias_of': canonical if str(name or canonical) != canonical else None,
    }



def get_dataset_desc(name: str) -> str:
    canonical = _canonical_dataset_name(name)
    return _DATASET_CANONICAL[canonical]['desc']



def get_exp_problems(dataset: str, sample_cnt: int) -> list[dict]:
    pool = _DATASET_ALIAS.get(dataset or 'custom', _FUNC_POOL)
    if not pool:
        return []
    n = max(1, int(sample_cnt or 1))
    limit = min(n, len(pool))
    rows: list[dict] = []
    for idx in range(limit):
        base = deepcopy(pool[idx])
        base['problem_no'] = idx + 1
        base['source_idx'] = idx + 1
        rows.append(base)
    return rows


assert len(_FUNC_POOL) == 20
assert len(_CLASS_POOL) == 20
assert len(_FILE_POOL) == 20
