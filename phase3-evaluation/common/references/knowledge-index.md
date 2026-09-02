# Phase3 共同知识索引

按以下顺序加载，避免把模板、黄金事实与评分标准混为一谈。

1. [页面模型](page-model.md)：页面定位、模块拓扑、可选/必选边界和治理原则。
2. [卡片结构与适用性规范](card-specification.md) 与根目录 `card-type-registry.v1.json`：卡型、变体、区域、槽位、实体边界与比较约束；后者是 Phase2 与 Phase3 共用的 id/展示名称唯一来源。
3. [黄金事实契约](golden-fact-contract.md)：Phase2 黄金 JSON 的机器事实边界、当前图优先和不确定性处理。
4. 本次被选维度的共享契约，再读每个被选叶子 Skill；评分阈值、`weight` 和 `aggregate` 只以叶子 Skill 为准。

事实优先级：当前图已验收 Phase2 manifest > 本目录的页面/卡型/卡片规范适用规则 > 黄金 JSON 的结构范例 > 白皮书原则。后三级只能解释当前事实，不能填补当前事实。
