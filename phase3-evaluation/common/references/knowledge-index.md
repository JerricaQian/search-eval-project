# Phase3 共同知识索引

按以下顺序加载，避免把模板、黄金事实与评分标准混为一谈。

1. [页面模型](page-model.md)：白皮书提炼的页面定位、模块拓扑、可选/必选边界和治理原则。
2. [卡型分类](card-taxonomy.md) 与根目录 `card-type-registry.v1.json`：正式卡片及广告/异构兜底类型的区域、变体和字段关系；后者是 Phase2 与 Phase3 共用的 id/展示名称唯一来源。
3. [卡片规范知识库 v2](card-specification.v2.md)：8 类卡片的槽位、变体、层级和业务适用性；只解释当前 Phase2 已确认事实，不能补写当前屏字段或改写评分标准。导入差异与兼容性决定见[对齐记录](new-spec-alignment.md)。
4. [黄金事实契约](golden-fact-contract.md)：Phase2 黄金 JSON 的机器事实边界、当前图优先和不确定性处理。
5. 本次被选维度的共享契约，再读每个被选叶子 Skill；评分阈值、`weight` 和 `aggregate` 只以叶子 Skill 为准。

事实优先级：当前图已验收 Phase2 manifest > 本目录的页面/卡型/卡片规范适用规则 > 黄金 JSON 的结构范例 > 白皮书原则。后三级只能解释当前事实，不能填补当前事实。
