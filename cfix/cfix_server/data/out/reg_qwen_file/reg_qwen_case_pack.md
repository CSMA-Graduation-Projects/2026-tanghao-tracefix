# qwen 典型案例包

- provider / model：qwen / qwen3-coder-next
- dataset：file_ultra
- samples：8

## 修复成功案例

- 题号：#2
- 标题：InventoryLedger 库存账本模块
- 场景：file
- 选择原因：初始失败后被真实修复，适合展示完整成功闭环。
- 轮次：1
- 通过情况：5/6 -> 6/6
- 最新动作：accept
- 根因：错误发生在调用 apply_ops 时，代码直接调用了 apply_ops(...) 而未通过类名 InventoryLedger.apply_ops(...) 调用，因为 apply_ops 是类的静态方法，必须通过类名访问；但更根本的问题是：题目要求模块中定义 apply_ops 作为独立函数（或类方法），而当前代码将其定义为静态方法，导致外部无法直接调用；此外，错误信息显示调用时未加类名前缀，说明调用方式与定义方式不匹配。
- 修复方案：1. 将 apply_ops 从静态方法改为模块级独立函数，使其可被直接调用；2. 或保留为静态方法，但调用时需用 InventoryLedger.apply_ops(...)；根据题目描述‘模块中必须定义...apply_ops(ops, initial=None)’，应定义为模块级函数；3. 修改代码：移除 @staticmethod 装饰器，将 apply_ops 移出类定义，作为顶层函数；4. 函数内部仍可复用 InventoryLedger 类，但需显式传入 initial 参数；5. 确保模块顶层提供该函数，满足题目‘直接生成一个完整的 Python 模块’的要求。
- 轨迹摘要：异常收敛点: NameError: NameError: name 'apply_ops' is not defined @L108

## rollback 生效案例

- 当前回归结果中暂无该类型案例。

## 最终失败案例

- 当前回归结果中暂无该类型案例。
