---
name: phase4-issue-evidence
description: 对 Phase3 已判定为问题的单一元素或组件/卡片生成整页截图红框证据图；单一元素保留精确定位但以所属组件/商卡作为红框上下文，组件/卡片只框选其整体区块，并回写评测结果供 Phase5 报告与人工复核使用。
---

# Phase4 问题证据标注

## 定位

本阶段位于 Phase3 多维度评测之后、Phase5 报告之前。它不重新识别页面、不改变评级、分数、`overview.total` 或问题计数；只为 Phase3 已判定为问题的可见区域生成原始尺寸的整页截图红框证据图，服务于报告展示与人工复核。

## 输入

- Phase3 最终评测结果：`.artifacts/过程文件-评测结果与审计/<batchId>/<query>/<tag>/results/评测原始结果_<query>[_<tag>]_<dimension>.json`；单词默认批次为 `单词运行`，`tag` 为空时不产生对应路径段/文件后缀。
- Phase2 统一元素清单及其审计文件：`screenshots-out/elements_<query>.json`、`.audit.json`。
- 原始截图：由清单顶层 `screenshot` 或每个评测单元 `details.screenshot` 指向。

## 输出

- 证据图目录：`screenshots-out/evidence/<query>/`。
- 结果回写：同一原始截图中的每个待优化问题（达标或不达标）共用同一张：
  - `evidenceImage`：保持原始尺寸、以红框汇总标出该截图全部问题位置的整页 PNG 绝对路径。
  - `evidenceScope`：本阶段写入实际红框粒度，仅可为 `component` 或 `card`；它只记录证据展示口径，不改变 Phase3 的 `coord`、评级或计数。
  - 单一元素问题另写 `evidenceTargetElementId`、`evidenceTargetCoord`：保持其实际判定对象和精确坐标，明确红框是上下文而非将整个组件判为问题。
- 不生成裁剪图，也不生成整页 Phase2 全量元素标注 PNG；后者仅由 Phase2 的 `phase2Mode=full-annotation` 按需生成。

## 事实源、校验与修复边界（阻断）

- **Phase2 是唯一定位事实源：**若 Phase3/4 暴露元素遗漏、卡片/模块边界、业务归属或事实字段错误，必须先回到 Phase2 修正 manifest，并重新运行 `validate_element_manifest.py`；随后重建或复跑受影响 Phase3，再执行本 Phase4。禁止直接改写结果 JSON 来伪造坐标、边界或证据。
- **校验器是闸门：**本阶段只消费已通过 `validate_eval_results.py` 的 Phase3 结果，执行后必须使用 `validate_eval_results.py --require-evidence` 验收。任一校验失败都必须优先修复上游事实或重跑对应阶段，不能继续报告。
- **修复脚本非默认步骤：**`repair_*` 仅可处理其 docstring 明示的兼容/结构问题；不得借此改变评级、问题数量、事实证据或业务归属。语义变化必须回到 Phase2/Phase3 正式流程。
- **参数化运行：**命令中的 `results`、`manifest`、`output-dir` 必须均为当前 `projectDir / batch / query` 推导出的路径；不得使用固定搜索词、旧 `reports/`、机器专属路径或 `/tmp` 历史路径作为输入输出。

## 执行规则

1. 仅处理 `rating` 为 `达标` / `🟡` / `不达标` / `🔴`、且**已通过 Phase3 评测结果校验**的问题；优秀项、无问题项、标记为“需复核/待回退 Phase2”的问题不生成证据图。无可定位范围的结论仍须由 Phase5 以文字“无可定位证据，待人工定位”呈现，绝不得伪造红框。
2. **先按评测维度决定红框展示粒度，禁止按 `elementId` 一刀切：**
   - `phase3-single_element-eval`：评测与判定仍以当前问题的单一元素为准，`elementId`、原始 `coord` 及原文均不得改变；红框则使用该元素所属完整 `cardId` / `component` 区块坐标，并写入与 Phase2 清单一致的 `evidenceTargetElementId`、`evidenceTargetCoord` 供追溯。找不到元素精确坐标或所属组件/商卡边界时跳过绘制，不得猜测或降级为元素框。
   - `phase3-card_or_component-eval`：只框选问题所属组件/商卡的完整 `cardId` / `component` 区块坐标；即使 Phase3 为追溯而引用了标题、标签等 `elementId`，也**不得**框选该元素细节。一个组件有多个问题时只保留一个组件框。
   - `phase3-page_framework-eval`：仅在结果提供经 Phase2 `pageFacts.modules` 或页面区域事实确认的 `evidenceCoord` 时框选该模块/页面区域；页面级结论不得借用任一最小元素坐标。
3. **组件/卡片框必须复用 Phase2 全量标注的聚合边界经验：**优先取 Phase2 清单中对应 `cards[].coord`（或 `pageFacts.modules[].coord`），以完整的视觉/功能独立区块为边界；包含该卡/组件的头图、文字、标签和下挂等可见内容，但不吞并相邻卡片、卡间留白或其他模块。不得根据问题元素的局部坐标猜测、外扩或平移组件框。
4. **一张原始截图只生成一张证据图**：聚合该截图下所有 skill、Tab 与问题的已解析范围，在原图副本上一次性绘制全部红框；这些问题必须回写同一个 `evidenceImage`。不得按 issue、skill、Tab 或元素 ID 复制近似图片。
5. 每个证据文件都保持原始截图的完整尺寸，仅以红框标出问题上下文；Phase4 不加元素编号、文字标签、半透明遮罩或 Phase2 全量标注层。每个红框绘制前必须反向核对：组件/卡片框覆盖完整区块且不侵入相邻区块；单一元素问题必须另有 `evidenceTargetElementId`、`evidenceTargetCoord` 对应真实问题对象。范围无法从 Phase2 事实解析时跳过绘制并记录原因，不能猜测或将元素框作为替代。
6. `description` 必须保留 Phase3 的必要判定依据；本阶段不得新造问题理由。供给呈现质量问题还必须已具备字段适用性与可见缺失证据；信息冗余问题还必须已具备两个独立实体、语义角色与无信息损失的证据。
7. 若 `评测结果校验_*.json` 中 `phase2ReviewRequired=true`，必须停止本阶段与报告阶段；读取同目录 `待回退Phase2复核_*.json`，由 Phase2 对列出的坐标和卡片重新整图识别/按需局部复核，更新清单与 `recognition-audit` 后重新执行 Phase3。
8. 运行后必须用 `validate_eval_results.py --require-evidence` 校验：每个已成功解析定位范围的待优化问题都有实际存在的整页红框证据图。

## 执行命令

```bash
python3 scripts/generate_issue_evidence.py \
  --results <评测结果绝对路径> \
  --manifest <项目根>/screenshots-out/elements_<query>.json \
  --output-dir <项目根>/screenshots-out/evidence/<query>

python3 scripts/validate_eval_results.py \
  --manifest-audit <项目根>/screenshots-out/elements_<query>.audit.json \
  --results <评测结果绝对路径> \
  --audit <评测审计绝对路径> \
  --require-evidence
```
