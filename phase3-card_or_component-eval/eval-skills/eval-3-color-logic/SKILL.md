---
name: eval-3-color-logic
title: 色彩运用逻辑性
weight: { "优秀": 1, "达标": 0, "不达标": -1 }
aggregate: "本维度按搜索词×组件，聚合到 Tab 级（取最差）。"
extra: ""
description: 搜索结果页组件色彩运用合理性评测；在需以红橙黄绿青蓝紫七色标准统计组件有效 UI 有彩色系时使用。
metadata: { author: qianjing16, version: "1.1", domain: 美团搜索结果页组件色彩逻辑评估 }
---

## 评审对象与共同契约

评审组件内有效 UI 的有彩色系数量，不把单一标签当作组件结论。先读 [[组件卡片评测通用契约]]（`phase3-card_or_component-eval/组件卡片评测通用契约.md`）。

## Phase2 与测量门槛

- 组件范围、图片、营销/金刚排除区与照片上独立 UI 角标只读 `pageFacts`、`structure`、`render`、`visual`。组件色彩只枚举 `cards[]`：Tab、图筛、业务图筛和筛选器是页面导航/查询收敛模块，必须排除，不能被提升为组件候选。
- 每个候选区域先确认是否属于有效 UI：照片、白色底图、金刚 icon 和纯营销素材应排除；叠在照片上的价格、标签或操作角标仍属于 UI，不能随照片一起排掉。
- 必须运行 `<projectDir>/phase3-evaluation-officer/scripts/extract_component_metrics.py` 或同等项目入口；脚本异常即阻断，LLM 不得目视填写像素数、色系或评级。
- 每个组件（包括优秀）保留 `assessmentRows`：`validUiPixelCount`、`excludedPhotoPixelCount`、`colorFamilies`、`colorFamilyCount`、`debugImage`、`measurement.tool/artifactPath/parameters` 和评级。

## 判定标准

HSV 中 `S<12` 为无彩色；`S≥12` 只归并为红、橙、黄、绿、青、蓝、紫 7 个色系：黄绿归绿，品红/紫红归紫，同一色系的明暗不拆分。渐变跨越一个色系计一种，跨越多个色系时每个面积占比不低于 1% 的色系各计一种。黑、白、灰不计；商家图片、下挂图片、营销图片/Banner/腰封、金刚图标、Tab、图筛、业务图筛、筛选器及面积占比 `<1%` 的颜色不计；标签（含图片上独立覆盖的 UI 标签）保留。

| 评级 | 有效 UI 有彩色系 |
|---|---|
| 优秀 | ≤3 |
| 达标 | 4–5 |
| 不达标 | ≥6 |

颜色结论只能来自脚本产物：先核对 debug 图的组件边界和 mask，再读取脚本给出的 `colorFamilies` 与 `colorFamilyCount`。debug 图用于发现 mask 错位，不允许手动增减色系。

## 评分与聚合

- 每张组件先按色系数评为优秀、达标或不达标；同一色系出现多处只算一种，不能按像素块重复计数。
- Tab 取全部组件的最差评级：任一不达标→不达标；否则任一达标→达标；全部优秀→优秀。
- Tab 仅写一个 `weightedScore = weight[rating]`：优秀 `1`、达标 `0`、不达标 `-1`，不按组件数量相加。

## 固定评审流程

1. 从 Phase2 确认每个组件边界，以及照片、营销区与独立 UI 角标的归属。
2. 运行测量，核查调试图中的边界和 mask；若 mask 与 Phase2 事实不符，回退修正事实或重跑测量。
3. 读取脚本色系数并按阈值评级；不得把肉眼颜色覆盖脚本结论。
4. 覆盖全部组件后取最差 Tab 评级，并写入唯一 `weightedScore`。

## 输出与反误判

- `overview.total` 为实际组件数，`evaluatedUnitCount` 与行数一致。
- `observableFact` 必须用中文色系、组件可见区域和同一行的实际计数；完整阈值写为“≤3 / 4–5 / ≥6”。
- 不把英文枚举、商家/下挂图片、营销素材、金刚图标、元素外背景或低占比杂色写入问题。

## Gotchas

- 相邻的两枚彩色标签不能因颜色接近合并；它们属于不同 UI 对象时均应进入测量。
- 渐变按脚本色相桶结果统计，不能因视觉上“是一种品牌色”手工压成一色。
- 调试图必须与实际组件 bounds 对应；范围漂移时先处理测量输入，不能继续给评级。
