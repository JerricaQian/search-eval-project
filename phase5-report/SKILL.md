---
name: report-local-html
description: >-
  美团搜索结果页本地 HTML 报告渲染层。用于 Phase4 完成后生成单词明细报告，或从当前隔离批次生成跨词治理看板。
  批量看板必须调用确定性生成器，不能由 Agent 自由编写或补造数据。
metadata:
  author: qianjing16
  version: "4.1"
  domain: 美团搜索结果页综合质量评估
---

# Phase5 本地报告

## 职责与边界

Phase5 只渲染已验收的 Phase2、Phase3、Phase4 事实：不重新评测、不计算分数、不改写评级、业务归属、问题数、坐标、证据或建议。

- 待优化问题仅为 `rating ∈ {达标, 不达标}`；优秀不作为问题展示。
- 有合法局部范围的问题必须使用 Phase4 整页红框 `evidenceImage`。页面级结论无局部范围时，只能复用同一原图已有的 Phase4 证据；没有可复用证据则显示“暂无截图证据”，不能伪造红框或用 Phase2 标注图替代。
- 任何元素清单、评测结果或事实字段校验失败，停止渲染并回退上游修复。

## 模板选择

| 输入范围 | 唯一模板 | 生成方式 |
|---|---|---|
| 单个搜索词 | `DETAIL_V1` | Agent 按本 Skill 的单词契约写入指定 HTML |
| 两个及以上搜索词的当前隔离批次 | `GOVERNANCE_DASHBOARD_V2` | 只运行 `phase5-report/scripts/build_experience_dashboard.py` |

不要创建第二份批量 HTML 生成器、旧版样式文件或并行渲染入口。

## `GOVERNANCE_DASHBOARD_V2`

### 唯一入口与命令

生产入口只有两层：

1. `phase5-report/scripts/build_experience_dashboard.py:collect()` / `validate_dataset()` 采集并阻断校验；`render()` 仅委派给渲染器。
2. `phase5-report/dashboard_renderer.py:render_dashboard()` 是唯一 HTML 渲染器。

批量看板必须使用下面的完整命令；所有路径只指向本轮隔离批次，禁止扫描全局历史产物。

```bash
"${pythonBin}" "${projectDir}/phase5-report/scripts/build_experience_dashboard.py" \
  --project-dir "${projectDir}" --artifact-dir "${batchArtifactDir}" \
  --batch-name "${batchId}" --output "${reportPath}" \
  --dataset-output "${reportDir}/.governance_dataset_${batchId}.json" \
  --expected-business-tabs "${expectedBusinessTabsCsv}"
```

`--expected-business-tabs` 是必填的、逗号分隔的标准 `businessCode` 精确集合。实际聚合的 Tab 缺失或多出任一项，生成器必须退出失败，不能以空卡、历史数据或默认 Tab 补齐。

### 数据与业务归属门槛

- 只消费当前批次已通过 `validate_element_manifest.py` 与 `validate_eval_results.py` 的产物；每个已评测词有原图，带坐标的待优化问题有 Phase4 证据，所有 `finding` 的 `observableFact`、`ruleOrThreshold`、`verdictReason`、`userImpact` 及问题级 `recommendation` 完整。
- 可用业务仅为：`dine_in`、`food_delivery`、`flash_delivery`、`service_retail`、`healthcare`、`hotel_travel`、`xiaoxiang`、`maoyan`。平台组件不进入业务 Tab。
- 若 Phase2 写明 `ownershipScope=business` 且 `businessCode` 为上述标准值，优先采用该明确归属；未知或不支持的显式 code 仍为 `unknown` 并阻断。
- 否则由当前卡片的可见商家/商品语义与履约事实判定：专属业态（医药、旅行、猫眼、小象）优先；服务零售次之；配送场景须同时具备餐饮或闪购品类事实；无配送的餐饮语义归到餐。卡片容器、搜索词、历史批次和 HTML 补丁都不能作为归属事实。
- 任何商卡证据不足即记录 `unknown` 并停止正式业务看板；先回到 Phase2 补充当前可见事实。

### 固定信息架构与视觉

看板采用参考版的浅色治理布局：`#F7F8FA` 画布、`1180px` 内容宽、白色表面、`#2563EB` 单一主交互色、`12px` 圆角和柔和低阴影。`dashboard_renderer.py` 内联唯一一套 CSS；不使用 CSS 叠加、历史样式块或同名覆盖。

固定结构：

1. 无顶部白色导航栏；标题区展示评测日期、搜索词数量、已执行维度和当前批次选择器。
2. 一级业务 Tab 吸顶，顺序为概览 + 本批次实际确认业务；激活项使用蓝色 `2px` 下划线。
3. 概览与业务页均使用一张“问题统计”综合卡：左侧为累计问题、本月新增、累计解决，中间为 P0/P1/P2 占比圆环，右侧为 TOP3 + 其他问题占比圆环；圆环中心不显示总数，悬停展示数量与占比。
4. 概览在统计卡后展示四列业务卡；业务卡显示新增数、累计问题和灰色 P0/P1/P2 标签，点击进入对应业务明细。
5. 业务明细使用“按问题 / 按搜索词 / 按指标”三级明细，默认“按问题”。
6. 每条问题展示优先级、所属搜索词、层级、对象、事实及用户影响、独立建议和 Phase4 证据；证据固定为 `240px × 180px`，懒加载并可新标签打开。

小屏下业务卡由四列降为两列再降为一列，问题图文改为单列；焦点态清晰，避免横向溢出。

明确禁止：Sankey 图和相关函数、页面级瀑布流/额外摘要区、重复问题证据、深色旧皮肤、CSS 分层覆盖、`render_v7_structured` 或任何未被 `render()` 调用的历史渲染器。

### 问题文案与排序

- 待优化项必须把正向评测指标转换为问题名称后写入 `metricName`，例如“信息无冗余 + 不达标”显示为“信息冗余”，“信息可比性 + 不达标”显示为“信息不可比”；禁止直接把正向指标名作为问题标题。
- 文案主体固定为“事实（含评级）→ 用户影响”；阈值和理由留在数据集供审计，不重复堆砌在卡片。
- `recommendation` 必须是问题级的：明确对象、动作和可验收结果；缺失时阻断，不能使用通用模板代替。
- 分组优先级由生成器按“业务线 + 维度 + 指标”统计，并按 P0 → P1 → P2 排序；渲染器只消费结果，不再计算。
- 同一截图的证据可在该截图的多个问题间复用；不同截图不得混用。

### 批量交付校验

生成后确认：

- HTML 与 `.governance_dataset_<batchId>.json` 均存在且非空；
- HTML 包含 `business-tab`、`business-panel`、`detail-tab`、`detail-pane`、`activateBusiness`；
- HTML 不包含 `sankey-link`、“高频问题跨词覆盖”或“典型问题证据库”；
- 业务 Tab 与 `--expected-business-tabs` 精确一致。

## `DETAIL_V1` 单词明细报告

单词报告不是批量看板的降级副本，也不调用独立 Python 渲染脚本。它只能读取 Stage D0 得到的 `computedJson`：

- 页头展示 `computedJson.scope.label`；当 `isFull=false`，紧随其后写明“部分评测，不能与完整19项综合分直接比较”。
- 展示本词各 Tab 的综合分、维度归一化分和评测项结果；问题展示其 Phase4 `evidenceImage`、事实、影响与独立建议。
- 不得从原始结果重算分数，不得伪造证据，不得把单词报告写成跨词业务聚合。

## 出口

本 Skill 只生成本地 `reports/` HTML 与批量数据集。NoCode、线上发布或数据库导入，须转交 `phase5-report/nocode-dashboard/SKILL.md`，并沿用同一份已验证数据集。
