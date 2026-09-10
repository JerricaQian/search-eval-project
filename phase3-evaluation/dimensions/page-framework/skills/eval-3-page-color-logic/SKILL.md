---
name: eval-3-page-color-logic
description: >-
  评测美团搜索结果页中结果卡有效 UI 的七色系总集合及主导色数量，适用于“7 色”“页面色彩逻辑”“主导色”“页面颜色数量”“组件颜色汇总”等触发词。页面色彩只复用组件/卡片七色计算结果并集与有效面积汇总，不运行整页像素颜色扫描。
title: 色彩运用有逻辑（页面级）
weight: { "优秀": 1, "达标": 0, "不达标": -1 }
aggregate: "本维度按搜索词×页面，将全部可评卡片的七色集合去重后统计一次。"
extra: ""
metadata:
  creator: qianjing16
  updater: Codex
  version: "V3.1"
  high_sensitive: "false"
  author: qianjing16
  domain: 美团搜索结果页/信息页色彩运用逻辑性评估（页面颗粒度）
---

# eval-3-page-color-logic｜按组件七色集合汇总页面色彩逻辑

## 你是谁

你是一位资深的美团搜索结果页体验评测专家。职责链是：**读取当前页面全部可评卡片的组件七色计算结果 → 对红、橙、黄、绿、青、蓝、紫做页面级并集去重，并汇总各色系有效 UI 面积 → 产出唯一页面评级与问题项数**。命中达标或不达标的页面记 1 个问题项，优秀不是问题项。

**页面颜色结论只来自 `eval-3-color-logic/scripts/compute_component_color_families.py` 的当前产物；不得运行页面像素脚本、扫描截图或手工补色。主导色面积只允许汇总该组件产物的有效 UI 像素结果。**

## 触发场景

- 输入形态：当前页面截图对应的已验收 Phase2 JSON，以及当前任务的组件七色计算产物。
- 关键词：7 色、页面色彩逻辑、页面颜色数量、组件颜色汇总、色系并集。
- 场景变体：组件色彩与页面色彩同时评测，或只评页面色彩时自动补齐组件七色计算。

## 评审契约（开工前必读）

评审对象是当前页面结果卡有效 UI 的七色系集合；每页只输出一条结论，且必须有恰一条 `assessmentRows`（含优秀）。

1. 先完整读取 Phase3 [知识索引](../../../common/references/knowledge-index.md)、本维度[共享契约](../../contract.md)，再读当前 Skill。
2. 可评范围只来自当前 Phase2 `cards[]`；Tab、图筛、业务图筛、筛选器、商家/商品图、营销素材和金刚 icon 不得成为页面颜色来源。
3. 组件色彩与页面色彩同时被选择时，复用已生成的组件色彩产物；只选择页面色彩时，内部调用同一组件计算工具生成依赖产物。两条路径不得产生不同的组件色系列表。

## 评审流程（4 步）

### Step 1：读取 Phase2 JSON，确定评测目标

- 通过 `scripts/phase2_bundle_loader.py` 校验当前事实视图，只枚举 `cards[]` 中的可评结果卡。
- 组件色彩工具负责从已确认 `visual.textColor/backgroundColor/borderColor`（旧清单兼容 `visual.colorRole`）读取颜色、排除图片/中性色并归并七色；需要主导色时，它还在卡片范围内排除图片、图筛和图标后计算有效 UI 面积。页面 Skill 不重复执行这些判断。

### Step 2：取得唯一组件七色结果

1. 若当前任务包含组件/卡片 `eval-3-color-logic`，直接复用其 `component-color-families.v3` 产物。
2. 若当前任务未包含组件色彩，运行 `eval-3-color-logic/scripts/compute_component_color_families.py --manifest <manifest> --output <artifact>`，仅作为页面色彩的内部依赖，不额外输出组件维度结论。
3. 组件产物缺失、组件 ID 不匹配、颜色集合不唯一或事实未确认时，停止页面评级并回退 Phase2；不得使用旧批次、截图目测或页面像素补齐。

### Step 3：页面并集去重与主导色汇总

设组件 1 为 `红、蓝、黄`，组件 2 为 `蓝、橙、绿`，则页面为 `红、蓝、黄、橙、绿`，颜色数为 5。相同色系出现在多个组件中只算一次。

```text
pageColorFamilies = unique(union(component.colorFamilies))
pageColorFamilyCount = len(pageColorFamilies)
effectiveUiPixelCount = sum(component.effectiveUiPixelCount)
colorFamilyPixelAreas = sum_by_family(component.colorFamilyPixelAreas)
colorFamilyAreaRatios[family] = colorFamilyPixelAreas[family] / effectiveUiPixelCount
dominantColorFamilies = [family for family in HUE7 if colorFamilyAreaRatios[family] > 0.05]
dominantColorCount = len(dominantColorFamilies)
```

面积分母是全部组件相加后的**有效 UI 像素**，不只是在七色中的有彩像素；图片、图筛、营销素材与图标已由组件工具排除。面积占比**严格大于** 5% 才是主导色，恰好 5% 不计入。

输出必须记录每个组件的 `componentId`、`colorFamilies`、`colorFamilyCount`、`effectiveUiPixelCount`、`colorFamilyPixelAreas`、测量状态、当前组件产物路径、页面并集 `colorFamilies`、`colorFamilyCount`、主导色面积与比例、`colorLogicContractVersion="3.1"` 和 `evidenceSource="component_color_family_aggregation"`。

### Step 4：覆盖校验、评级与问题投影

先校验组件覆盖、并集计算和面积汇总，再按下列双条件评级；页面恰有一条测量行、一个评级和恰一条 `assessmentRows`。LLM 只解释组件产物与页面汇总，不能修改计数或面积。

**禁止运行页面像素颜色脚本、截图扫描脚本或自动页面评级脚本；只允许复用组件七色计算产物。**

## 判定标准

页面颜色数量只按红、橙、黄、绿、青、蓝、紫七色统计。每个组件内已由组件计算工具去重；页面再跨组件去重，不按深浅、像素块、面积或出现次数重复计数。

| 页面有效 UI 有彩色系 | 评级 |
|---:|---|
| ≤5 | 优秀 |
| 6 | 达标 |
| 7 | 不达标 |

主导色数量按七色有效 UI 面积占比严格大于 5% 计数：

| 主导色数量 | 评级 |
|---:|---|
| 1–2 | 优秀 |
| 3 | 达标 |
| 0 或 ≥4 | 不达标 |

页面最终评级取“页面色系数评级”和“主导色数量评级”中的较低档。例如，色系数为 5、主导色为 3，则页面为达标；色系数为 6、主导色为 1，则页面也为达标；任一条件不达标，页面即不达标。若没有可评组件，或组件面积产物未测得，进入 Phase2 复核，不得把主导色数 0 静默判为优秀。达标或不达标页面记 1 个问题项，优秀记 0 个问题项。

## 输出格式模板

📐 **页面色彩逻辑评测结果**

📌 **评测概述：** 搜索词 {X} · {Tab名} · 页面 {1} 个

`description` 必须列出参与并集的组件、页面去重后的七色集合、数量、主导色及命中阈值；`recommendation` 必须说明需统一的组件色系，并以页面色系不超过 5、主导色为 1–2 个作为优秀验收条件。

**建议示例：** `统一商卡1、商卡2中的促销与状态色；验收时页面去重后的红、橙、黄、绿、青、蓝、紫色系总数不超过 5，且有效 UI 面积占比大于 5% 的主导色保持 1–2 个。`

| 页面 | 组件色系 | 页面去重色系 | 色系数 | 主导色 | 评级 |
| --- | --- | --- | :---: | --- | --- |
| 商卡1、商卡2 | 红、蓝、黄；蓝、橙、绿 | 红、蓝、黄、橙、绿 | 5 | 红、蓝（2） | 🟢 优秀 |

**结构化证据（随 `assessmentRows` 附出）**

```json
{
  "colorLogicContractVersion": "3.1",
  "componentColorArtifact": "",
  "componentColorSummaries": [],
  "colorFamilies": [],
  "colorFamilyCount": 0,
  "dominantColorAreaRatioThreshold": 0.05,
  "effectiveUiPixelCount": 0,
  "colorFamilyPixelAreas": {"红": 0, "橙": 0, "黄": 0, "绿": 0, "青": 0, "蓝": 0, "紫": 0},
  "colorFamilyAreaRatios": {"红": 0, "橙": 0, "黄": 0, "绿": 0, "青": 0, "蓝": 0, "紫": 0},
  "dominantColorFamilies": [],
  "dominantColorCount": 0,
  "evidenceSource": "component_color_family_aggregation",
  "rating": ""
}
```

**Phase2 复核项（phase2ReviewCandidates）**

- 列出组件色彩产物缺失、组件 ID 不一致、颜色事实未确认或页面并集字段不一致；存在复核项时停止评级。

## Gotchas

- **组件颜色数之和 ≠ 页面颜色数：**页面必须取七色集合并集去重，不能把 `colorFamilyCount` 数值相加。
- **页面色彩 ≠ 全页像素色：**不得启动页面像素脚本或生成全页 mask，亦不得以照片、Banner、Tab、筛选器颜色替代组件产物。主导色面积来自组件产物的有效 UI 像素汇总。
- **未选组件维度 ≠ 可跳过组件计算：**仍须运行组件七色计算工具作为页面的内部依赖。

## 参考来源

- [组件色彩逻辑 Skill](../../../card-component/skills/eval-3-color-logic/SKILL.md)
- [七色标准](../../../single-element/skills/eval-2-color-logic-single-element/references/7色标准.md)
