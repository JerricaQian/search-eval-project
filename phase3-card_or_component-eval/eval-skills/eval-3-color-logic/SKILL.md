---
name: eval-3-color-logic
title: 色彩运用逻辑性
weight: { "优秀": 1, "达标": 0, "不达标": -1 }
aggregate: "本维度按搜索词×组件，聚合到 Tab 级（取最差）。"
extra: ""
description: 搜索结果页组件色彩运用合理性评测；直接读取 Phase2 JSON 中已确认 UI 元素的样式色值，按红橙黄绿青蓝紫七色标准统计组件色系，不运行像素脚本。
metadata: { author: qianjing16, version: "1.2", domain: 美团搜索结果页组件色彩逻辑评估 }
---

## 评审对象与共同契约

评审组件内有效 UI 的有彩色系数量，不把单一标签当作组件结论。先读 [[组件卡片评测通用契约]]（`phase3-card_or_component-eval/组件卡片评测通用契约.md`）。

## Phase2 JSON 颜色门槛

- 通过 `scripts/phase2_bundle_loader.py` 校验并读取 Phase2 JSON。组件色彩只枚举 `cards[]`；Tab、图筛、业务图筛和筛选器属于页面导航/查询收敛模块，不能被提升为组件候选。
- 遍历组件全部活动原子，只读取 `visualStatus=confirmed` 的 `visual.textColor/backgroundColor/borderColor`。照片、营销素材、金刚 icon 和纯白底图排除；照片上有独立 Phase2 原子的标签或操作角标仍保留。
- 对每个样式色值直接做 HSV 归并：`S<12` 为中性色，`S≥12` 归入红、橙、黄、绿、青、蓝、紫。同一色值或同一色系出现多次只计一种；不根据元素面积或像素占比过滤。
- 本 Skill 禁止运行 `extract_component_metrics.py`、OpenCV 或其他像素颜色脚本。任一活动 UI 原子的颜色事实缺失或未确认时回退 Phase2，不允许从截图目测补色。
- 每个组件（包括优秀）保留 `assessmentRows`：`componentId`、`scannedElementIds`、`excludedElementIds`、`sourceColorValues`、`colorFamilies`、`colorFamilyCount`、`evidenceSource=phase2_json_visual_colors` 和评级，不得附带 `measurement`。

## 判定标准

HSV 中 `S<12` 为无彩色；`S≥12` 只归并为红、橙、黄、绿、青、蓝、紫 7 个色系：黄绿归绿，品红/紫红归紫，同一色系的明暗不拆分。若 JSON 颜色值显式包含多个渐变色标，逐个归并；没有发布的渐变停靠点不从像素反推。黑、白、灰、商家/下挂图片、营销素材、金刚图标不计；有独立原子的 UI 标签保留。

| 评级 | 有效 UI 有彩色系 |
|---|---|
| 优秀 | ≤3 |
| 达标 | 4–5 |
| 不达标 | ≥6 |

颜色结论只能来自当前 JSON 颜色库存：`sourceColorValues` 保留元素 ID、颜色字段、原色值和归并色系，`colorFamilies` 是其去重集合。LLM 不得手动增减色系。

## 评分与聚合

- 每张组件先按色系数评为优秀、达标或不达标；同一色系出现多处只算一种，不能按像素块重复计数。
- Tab 取全部组件的最差评级：任一不达标→不达标；否则任一达标→达标；全部优秀→优秀。
- Tab 仅写一个 `weightedScore = weight[rating]`：优秀 `1`、达标 `0`、不达标 `-1`，不按组件数量相加。

## 固定评审流程

1. 从 Phase2 JSON 确认每个组件的全部活动原子，以及照片、营销素材与独立 UI 角标的归属。
2. 逐原子读取已确认样式色值，记录纳入/排除理由，并建立 `sourceColorValues`。
3. 将非中性色值归并为七色并去重，按 `colorFamilyCount` 套阈值评级；不得回看截图补色或覆盖 JSON 结论。
4. 覆盖全部组件后取最差 Tab 评级，并写入唯一 `weightedScore`。

## 输出与反误判

- `overview.total` 为实际组件数，`evaluatedUnitCount` 与行数一致；每行的 `evidenceSource` 必须为 `phase2_json_visual_colors`。
- `observableFact` 必须用中文色系、组件可见区域和同一行的实际计数；完整阈值写为“≤3 / 4–5 / ≥6”。
- 不把英文枚举、商家/下挂图片、营销素材、金刚图标、元素外背景或低占比杂色写入问题。

## Gotchas

- 相邻的两枚彩色标签不能因文案或位置接近而合并元素；但它们归入同一七色色系时，组件色系数只计一种。
- 不得用元素面积、像素占比或测量脚本重新解释 JSON 色值；样式色值不完整时必须回退 Phase2。
