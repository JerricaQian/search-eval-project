---
name: eval-3-color-logic
description: >-
  评测搜索结果页卡片组件有效 UI 的有彩色系数量，并产出供页面主导色条件复用的七色有效面积；触发词包括组件色彩、七色标准、颜色逻辑、色系数量、中性色门槛。即使未明确提及色彩运用逻辑，只要需要按 Phase2 JSON 样式色值统计组件红橙黄绿青蓝紫色系，就应激活。
title: 色彩运用逻辑性
weight: { "优秀": 1, "达标": 0, "不达标": -1 }
aggregate: "本维度按搜索词×组件，聚合到 Tab 级（取最差）。"
extra: ""
metadata:
  creator: qianjing16
  updater: Codex
  version: "V3.1"
  high_sensitive: "false"
  author: qianjing16
  domain: 美团搜索结果页组件色彩逻辑评估
---

# eval-3-color-logic：以 JSON 色值统计组件有效 UI 色系

---

## 你是谁

你是一位资深的美团搜索结果页体验评测专家。职责链是：**基于已确认 UI 原子的 `visual.textColor/backgroundColor/borderColor`（兼容已确认的旧版 `visual.colorRole`）→ 运行唯一组件七色计算工具 → 按组件计数，并产出有效 UI 中的七色像素面积 → 产出评级、问题项数、排除项、复核项与可追溯证据**。

**色系归类只来自 Phase2 JSON，绝不像素级主观扫描。**当页面色彩同时被选择时，计算器可在已确认的卡片范围内对当前截图作确定性像素面积统计；这只服务页面主导色条件，不改变组件色系数量。达标或不达标组件记为一个问题项，优秀不是问题项；同一组件命中多条问题也只计一个问题项，不按问题条数倍乘。

---

## 触发场景

- 输入形态：经 loader 校验的 Phase2 JSON 样式色值库存。
- 关键词：组件色彩、七色标准、颜色逻辑、色系数量、中性色、colorFamilyCount。
- 场景变体：商卡、商品卡、照片上独立 UI 标签或操作角标。

---

## 评审契约（开工前必读）

评审组件内有效 UI 的有彩色系数量，不把单一标签当作组件结论。先读本维度[共享契约](../../contract.md)。

1. **先完整读取本维度共享契约和当前 Skill，当前 Phase2 事实优先。**
2. **排除项必须显式入账，全部适用区域/组件/比较组必须覆盖，不擅自合并。**
3. **事实或覆盖不足必须进入复核；宁可不出结论，不得静默产出优秀或问题。**

---

## 评审流程（4 步）

### Step 1：读取 Phase2 JSON，确定评测目标

- 通过 `scripts/phase2_bundle_loader.py` 校验并读取 Phase2 JSON。组件色彩只枚举 `cards[]`；Tab、图筛、业务图筛和筛选器属于页面导航/查询收敛模块，不能被提升为组件候选。兼容旧清单时，即使图筛被错误投影为卡片，计算器也必须按 `image_filter`、`business_image_filter`、`图筛` 或 `业务图筛` 类型显式跳过。
- 遍历组件全部活动原子，只读取 `visualStatus=confirmed` 的 `visual.textColor/backgroundColor/borderColor`；旧版清单没有 CSS 色值时，复用已确认的 `visual.colorRole`。照片、营销素材、金刚 icon 和纯白底图排除；照片上有独立 Phase2 原子的标签或操作角标仍保留。
- 对每个样式色值先使用统一感知中性色门槛：仅当 `S≥15、V≥20、RGB绝对色度≥20` 同时成立才进入红、橙、黄、绿、青、蓝、紫归并；带轻微色偏的近黑、灰褐、灰蓝均排除。同一色值或同一色系出现多次只计一种；不根据元素面积或像素占比过滤。
- 必须运行 `scripts/compute_component_color_families.py` 取得组件七色结果；它只读取 Phase2 JSON，不扫描截图像素。任一活动 UI 原子的颜色事实缺失或未确认时回退 Phase2，不允许从截图目测补色。
- 每个组件（包括优秀）保留 `assessmentRows`：`componentId`、`scannedElementIds`、`excludedElementIds`、`sourceColorValues`、`colorFamilies`、`colorFamilyCount`、`evidenceSource=phase2_json_visual_colors` 和评级，不得附带 `measurement`。

### Step 2：先排除，再成立，最后处理例外

1. **先排除：**执行本 Skill 原文规定的所有不适用对象、白名单、自然裁切、非候选关系与证据不足项，并逐项记录理由。
2. **再成立：**只对满足当前 Skill 对象、事实门槛和成立条件的候选继续计数或比较。
3. **最后处理例外：**执行原文的核心字段、业务变体、运营差异、嵌套/覆盖或其他专属例外；不得因位置、文案或视觉印象擅自合并。

### Step 3：执行专属扫描、测量或关系核查

1. 运行 `scripts/compute_component_color_families.py --manifest <manifest> --output <artifact>`；当前组件色彩评测与页面色彩兜底必须复用同一产物，不能二次归类。
2. 从脚本产物读取每个组件的全部活动原子、`sourceColorValues`、`neutralColorValues`、排除项与去重后的 `colorFamilies`。页面色彩被选择时，同时读取 `effectiveUiPixelCount`、`colorFamilyPixelAreas` 与 `dominantColorMeasurementStatus`；面积由卡片边界内有效 UI 像素统计，已确认图片和图筛区域不进入分母或分子。
3. 按 `colorFamilyCount` 套阈值评级；不得回看截图补色或覆盖脚本 JSON 结论。
4. 覆盖全部组件后取最差 Tab 评级，并记录问题项。

### Step 4：覆盖校验、评级与问题投影

1. **校验覆盖完整性：**执行时目标与覆盖记录必须包含本 Skill 要求的全部评估单位和证据字段；有未扫描对象、静默原子或复核项即停止相应评级，宁可不出结论。
2. **先归类后读数：**先完成纳入、排除、例外与候选终判，再读取计数、间隔、层级或冲突/重复数量。
3. **按阈值判级并落问题项：**严格使用下方原始判定标准；达标或不达标组件各计一个问题项，优秀不计问题项。

- 日常结论只呈现**评级 + 问题项数**；不输出“评级分布汇总（按搜索词×Tab）”表。
- 评级聚合备注如下：

> 每张组件先按色系数评为优秀（≤4）、达标（5）或不达标（≥6）；同一色系出现多处只算一种，不能按像素块重复计数。
> Tab 取全部组件的最差评级：任一不达标→不达标；否则任一达标→达标；全部优秀→优秀。

- 除 `scripts/compute_component_color_families.py` 外，禁止运行 `extract_component_metrics.py`、OpenCV 或其他颜色脚本；不得附带 `measurement`。

---

## 判定标准

JSON 色值仅在 `S≥15、V≥20、RGB绝对色度≥20` 同时成立时视为有彩色，再归并为红、橙、黄、绿、青、蓝、紫 7 个色系：黄绿归绿，品红/紫红归紫，同一色系的明暗不拆分。若 JSON 颜色值显式包含多个渐变色标，逐个归并；没有发布的渐变停靠点不从像素反推。黑、白、灰、感知近黑/灰色、商家/下挂图片、营销素材、金刚图标不计；有独立原子的 UI 标签保留。

| 评级 | 有效 UI 有彩色系 |
|---|---|
| 优秀 | ≤4 |
| 达标 | 5 |
| 不达标 | ≥6 |

颜色结论只能来自当前 JSON 颜色库存：`sourceColorValues` 保留元素 ID、颜色字段、原色值和归并色系，`colorFamilies` 是其去重集合。LLM 不得手动增减色系。

---

## 输出格式模板

📐 **组件色彩逻辑评测结果**

📌 **评测概述：** 搜索词 {X} · {Tab名} · 完整可评组件 {N} 个

Phase5 问题卡由 `assessmentRows` 中评级为达标或不达标的问题行一对一生成：`description` 写该行事实、命中规则、评级原因与直接影响；`recommendation` 写“调整对象 + 具体动作 + 本 Skill 优秀档验收条件”；Phase4 回写 `evidenceImage`。

原有字段与示例锚点（保持原口径）：`evaluatedUnitCount`、`evidenceSource`、`overview.total`、`phase2_json_visual_colors`、“≤4 / 5 / ≥6”。

---

**评测明细（assessmentRows）**

| 组件 | 组件类型 | 标签/元素文案 | 色系（列举） | 色系数 | 评级 |
| --- | --- | --- | --- | :---: | --- |
| 商卡3 · {名称} | 商品卡 | 夏日特惠、立享9.3折 | 红、橙、黄、绿、蓝 | 5 | 🟡 达标 |

**填写示例：** 上表最后一行展示真实文案、实际数量和对应评级；正式输出时逐一替换为当前页面事实，不使用内部 ID 充当用户可读文案。

> `description` 必须基于对应问题行写清实际对象、计数或比较结果、命中规则、评级原因与直接影响；`recommendation` 必须给出调整对象、具体动作和本 Skill 优秀档验收条件。

**建议示例：** `统一商卡3中“夏日特惠、立享9.3折”等 UI 标签的色彩角色并减少色系；验收时确认有效 UI 有彩色系不超过 4，评级达到优秀。`

**结构化证据（随 `assessmentRows` 附出）**

```json
{
  "componentId": "",
  "scannedElementIds": [],
  "excludedElementIds": [],
  "sourceColorValues": [],
  "neutralColorValues": [],
  "colorFamilies": [],
  "colorFamilyCount": 0,
  "evidenceSource": "phase2_json_visual_colors"
}
```

**排除对象（excludedUnits）**

| 组件/区域 | 标签/元素文案 | 排除原因 |
| --- | :---: | --- |
| 商家图片 | 商家/下挂图片 | 照片素材不计 UI 色系 |

**Phase2 复核项（phase2ReviewCandidates）**

- 逐项列出组件、缺失样式事实、复核原因与请求动作；有复核项停止评级。
- 复核项只承载当前 JSON 中未确认、归属缺失或事实不完整的对象；**存在复核项时不得给出正式评级**。

**总结说明：** 汇总达标与不达标组件的超阈色系、优秀组件的色彩特征与改进建议；达标或不达标组件计问题项。 Phase5 只展示达标/不达标问题项；优秀仅保留评级解释，不进入发现问题或治理项。

---

## Gotchas

- **相邻彩色标签 ≠ 同一元素**；相邻的两枚彩色标签不能因文案或位置接近而合并元素；但它们归入同一七色色系时，组件色系数只计一种。
- **组件色系数 ≠ 页面主导色数**；组件评级只读 JSON 色系数，不被像素面积改变。页面需要主导色时，只能复用本计算器输出的有效 UI 面积，不能另起页面脚本。

---

## 参考来源
