---
name: run-eval
description: 使用本项目五阶段评测工作流；支持默认 Phase2 轻量识别、可选全量标注、Phase4 问题局部证据和 Phase5 报告。
---

# 运行评测工作流

用户要求运行本项目评测、对已有截图评测、现场截图后评测或生成报告时使用本技能。

## 执行入口与回退

优先使用项目根目录下的显式 Workflow：

```text
workflow/meituan_eval_workflow.js
```

当当前会话提供 Workflow 工具时，传入本 Skill 的 args 调用该脚本。它依赖宿主注入 `args`、`agent`、`parallel`、`phase`、`log`，因此不能直接用 Node.js 执行。

若 Workflow 工具未注入、宿主运行时不可用，或用户明确要求逐阶段执行，必须改用 **Agent 任务编排** 完整执行相同的 phase1 → phase2 → phase3 → phase4 → phase5；这不是降级评测。**创建 TODO 或执行 phase1 前，必须通过结构化提问向用户确认：**① 是否执行默认 Phase2 轻量识别或全量标注；② 要评测哪些维度（可多选：单一元素、组件/卡片、页面框架）；③ 需要仅交付本地 HTML，还是在本地 HTML 完成后继续生成/部署 NoCode 报告。Agent 必须按本项目各 phase 的 SKILL.md、确定性审计器和固定输出目录执行，不得跳过统一元素清单、`validate_element_manifest.py`、`validate_eval_results.py`、Phase4 局部问题证据或 Phase5 报告契约。用户选择 NoCode 时，必须先完成本地报告或批量治理数据集，再遵循 `phase5-report/nocode-dashboard/SKILL.md` 处理线上出口。只有在两种入口均因真实环境依赖失败时，才报告失败阶段和可执行修复动作。

### 批量调度与过程保留纪律

- 多搜索词任务严格按批次执行：每批最多并发 **3 个子代理**，每个子代理只处理 **1 个搜索词**；必须等待整批完成后再启动下一批。不得把多个词交给一个子代理，也不得按单个 eval skill 拆出超出词级上限的并发。
- 为每个子代理 prompt 明示批次号、唯一搜索词、输入截图和目标输出目录；某词失败时只重试该词。
- 不删除过程文件、图片、裁剪图、扫描输出、审计结果或失败产物。需要隔离的中间文件一律写到 `.artifacts/过程文件-评测结果与审计/<批次>/<搜索词>/<阶段>/`，保留路径及失败原因供复盘。

## 运行前检查

1. 默认复用已有截图：`skipScreenshot=true`。确认 `screenshots/` 下存在目标搜索词截图。
2. 用户明确要求现场截图时才设 `skipScreenshot=false`；先运行 `bash setup.sh --with-device`，确认 Android 设备在线、美团 App 已登录。
3. Phase2 默认运行轻量识别（`annotate` 省略或为 true，`phase2Mode=lightweight`），只输出统一元素清单 JSON 到项目级 `screenshots-out/`；用户明确需要整页标注 PNG 时设 `phase2Mode=full-annotation`。
4. 过程文件由工作流写入 `.artifacts/过程文件-评测结果与审计/`，最终 HTML 只写入 `reports/`。

## 默认参数

```json
{
  "query": "<用户给定搜索词>",
  "dimensions": ["phase3-card_or_component-eval"],
  "tabs": ["全部"],
  "screens": ["1"],
  "skipScreenshot": true,
  "phase2Mode": "lightweight"
}
```

除非用户明确要求，不要擅自扩大到多个 Tab、多个屏或所有评测维度。三类维度均可组合：`phase3-single_element-eval`、`phase3-card_or_component-eval`、`phase3-page_framework-eval`。

## 常用场景

### 评已有截图

```json
{
  "query": "库迪",
  "dimensions": ["phase3-card_or_component-eval"],
  "tabs": ["全部"],
  "screens": ["1"],
  "skipScreenshot": true,
  "phase2Mode": "lightweight"
}
```

### 现场截图后评测

```json
{
  "query": "库迪",
  "dimensions": ["phase3-card_or_component-eval"],
  "tabs": ["全部", "外卖", "团购"],
  "screens": ["1", "2", "3"],
  "skipScreenshot": false,
  "phase2Mode": "lightweight"
}
```

## 完成标准

- 返回最终 HTML 的绝对路径；
- 说明使用的截图数、Phase2 模式（轻量/全量）、Phase4 局部证据数量、各维度数量；
- 若失败，说明失败阶段与可执行的修复动作；
- 不把 `.artifacts/` 的过程文件当作最终交付物。
- 用户要求跨词治理、NoCode 线上看板或部署时：先确保由 `scripts/build_experience_dashboard.py` 生成本地治理 HTML 与同批 `.governance_dataset_<批次>.json`，再切换到 `phase5-report/nocode-dashboard/SKILL.md` 处理数据导入、证据图发布和部署；不要由本 Skill 绕过该出口。
