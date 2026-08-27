---
name: eval-6-info-partitioning
title: 信息分区合理性
weight: { "优秀": 1, "不达标": -1 }
aggregate: "本维度按问题数量 N 评级：N=0→优秀，N≥1→不达标，两档无中间档。聚合到 Tab 级按最差值：该 Tab 下任一组件存在分区边界不清晰（N≥1）即该 Tab 不达标；全部组件 N=0 则该 Tab 优秀。"
extra: ""
description: 搜索结果页组件内信息分区评测；直接读取 Phase2 JSON 的相邻分区及元素坐标，以内容包围盒之间是否存在正向间隔判断分区，不运行像素测量脚本。
metadata: { author: qianjing16, version: "1.2", domain: 美团搜索结果页组件信息分区评估 }
---

## 评审对象与共同契约

评审单个组件内部、且由 Phase2 确认的相邻功能分区；不评组件之间、跨 Tab 或跨屏的边界。先读 [[组件卡片评测通用契约]]（`phase3-card_or_component-eval/组件卡片评测通用契约.md`）。

## Phase2 JSON 坐标门槛

- 通过 `scripts/phase2_bundle_loader.py` 校验并读取 Phase2 JSON；分区、元素归属、坐标与可见状态是唯一事实来源。不得为本 Skill 运行 `extract_component_metrics.py`、OpenCV 或其他截图像素测量脚本。
- 每个分区的内容包围盒取该分区全部活动元素坐标的并集，不使用可能重叠或留白较大的分区外框判断间隔。整张商卡范围包含头图、基础信息、标签/价格和下挂，不能只看“标签区”。
- 候选只能是 Phase2 已确认、同一组件内且实际相邻的两个功能分区。组件之间、跨 Tab、跨屏续接、分区内部的字段间距都不进入候选集。
- 若任一分区没有可用活动元素坐标，当前分区对写入 `excludedPairs` 并回退 Phase2；不得用区域外框、截图观感或默认值补造间隔。
- 每个组件保留 `assessmentRows`：带 `region/elementIds/contentBounds` 的 `partitions`、`adjacentBoundaryChecks`、`excludedPairs`、`issueCount` 和评级；`overview.total` 为组件数。

## 判定标准

只对确认相邻的分区对判断 JSON 内容包围盒间隔。沿相邻方向存在任何正向间隔（`gapPx > 0`）即认为分区清楚；不再与区域内部间距比较，不计算 `1.5×` 阈值，也不计算 RGB、前景色或背景色差值。

| 评级 | 条件 |
|---|---|
| 优秀 | 当前 Tab 所有可测相邻分区对的 JSON 内容包围盒均有正向间隔，且问题数为 0 |
| 不达标 | 同一相邻分区对的内容包围盒在阅读轴上发生接触或重叠（`gapPx≤0`），计 1 项；任一组件累计≥1 |

“未测得”“坐标缺失”“无法确认”“非候选对”不是边界接触或重叠，必须排除并回退 Phase2，不能制造问题或优秀证据。`gapPx` 直接由两个分区的内容包围盒计算，LLM 不得改写。

## 评分与聚合

- 每个组件的 `issueCount` 是 JSON 坐标确认 `gapPx≤0` 的相邻分区对数；同一对最多计一次。
- 所有组件的 N=0 时 Tab 为优秀，任一组件有 N≥1 时 Tab 为不达标。测量不足的对必须被排除并保留原因，不能转写为问题。
- Tab 只写一个 `weightedScore = weight[rating]`：优秀 `1`、不达标 `-1`，不按问题对数累计。

## 固定评审流程

1. 遍历整张组件，从 Phase2 JSON 枚举已确认的相邻功能分区对；先写清哪些对因非相邻、跨组件、自然截断或坐标不足而排除。
2. 对每个分区汇总活动 `elementIds`，直接计算元素坐标并集 `contentBounds`。
3. 根据相邻方向计算两个 `contentBounds` 的 `gapPx`：`gapPx>0` 为清楚；`gapPx≤0` 计一项；坐标不足进入 `excludedPairs`，不评级为问题。
4. 汇总组件与 Tab 的问题数、评级和唯一分数；输出证据来源 `phase2_json_coordinates`，不得附加像素测量产物。

## 输出与反误判

- 问题必须指向组件和分区对，并保留双方 `elementIds/contentBounds`、阅读轴和 `gapPx`；同一对最多计一次。
- 正常字段留白、分区缺失、组件间边界和测量不足不计入；宁少报，不把空扫描结果当无边界。

## Gotchas

- 只要内容包围盒之间存在正向间隔就已经分区清楚，不要求该间隔大于内部间距，也不要求分割线或颜色差。
- 不计算区域整体 RGB 中位数，不用颜色差阈值推断边界。
- 分区本身未展示属于供给问题，不把它转化为“两个分区没有边界”。
