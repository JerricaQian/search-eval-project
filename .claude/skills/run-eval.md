---
name: run-eval
description: 使用美团搜索评测 1.0 Workflow：仅截图、仅评测已有截图，或截图后确认评测的全流程。
---

# 运行评测工作流（1.0）

用户请求截图、评测已有截图、现场截图后评测或生成报告时使用本技能。入口为：

```text
workflow/meituan_eval_workflow.js
```

该 Workflow 依赖宿主注入的 `args`、`agent`、`parallel`、`phase`、`log`，不能直接使用 Node 运行。

## 先确认任务模式

先让用户选择一项：

1. **仅自动化截图**
2. **仅评测已有截图**
3. **自动化截图 + 评测**

只询问当前模式需要的参数，不能提前追问无关项目。

| 模式 | 询问 | 不询问 |
|---|---|---|
| 仅自动化截图 | 搜索词、Tab、屏数 | 评测维度、报告出口 |
| 仅评测已有截图 | 截图范围、评测维度、报告出口 | 搜索词、Tab、屏数、设备参数 |
| 截图 + 评测 | 先问搜索词、Tab、屏数；截图成功后再问维度、报告出口 | — |

## 调用方式

所有调用必须显式传入 `projectDir`。

### 1. 仅自动化截图

```json
{
  "mode": "capture_only",
  "projectDir": "<项目绝对路径>",
  "query": "库迪",
  "tabs": ["全部", "外卖"],
  "screens": ["1", "2"]
}
```

Workflow 只调用 Screenshot Agent，返回 `screenshots/` 中本次有效图片的路径。

### 2. 仅评测已有截图

第一轮只发现截图，不输入搜索词：

```json
{
  "mode": "evaluate_only",
  "projectDir": "<项目绝对路径>",
  "discoveryOnly": true
}
```

Workflow 返回可选截图组。用户选择同一搜索词的一组 `files` 后再调用。`query` 由文件名推导，不需向用户重复询问：

```json
{
  "mode": "evaluate_only",
  "projectDir": "<项目绝对路径>",
  "selectedScreenshots": ["<截图绝对路径>"],
  "dimensions": ["phase3-card_or_component-eval"],
  "reportOutlet": "local_html",
  "phase2Mode": "lightweight"
}
```

截图命名必须为 `<搜索词>_<Tab>_<屏>.png`。无法解析时，由调用方补充系统推导出的 `query`，而不是要求用户重复输入搜索词。

### 3. 自动化截图 + 评测

第一轮只执行截图：

```json
{
  "mode": "capture_and_evaluate",
  "projectDir": "<项目绝对路径>",
  "query": "库迪",
  "tabs": ["全部", "外卖", "团购"],
  "screens": ["1", "2", "3"]
}
```

它返回 `awaiting_evaluation_config` 及截图路径。截图成功后，再询问用户评测维度和报告出口，并使用返回的路径发起第二轮：

```json
{
  "mode": "evaluate_only",
  "projectDir": "<项目绝对路径>",
  "selectedScreenshots": ["<第一轮返回的截图绝对路径>"],
  "dimensions": ["phase3-card_or_component-eval"],
  "reportOutlet": "local_html",
  "phase2Mode": "lightweight"
}
```

`reportOutlet` 可为 `local_html` 或 `nocode`。选择 `nocode` 时，仍须先完成本地 HTML 和治理数据集，再按 `phase5-report/nocode-dashboard/SKILL.md` 获得用户授权后处理线上出口。

## Evaluation Agent 的固定约束

Evaluation Agent 在同一上下文内执行 Phase2 → Phase3 → Phase4 → Phase5：

- 每张截图一个独立 manifest；
- Phase2 默认本地轻量识别，必须通过 `validate_element_manifest.py`；
- Phase3/4 必须通过 `validate_eval_results.py`，Phase4 使用 `--require-evidence`；
- Phase5 只消费验收结果；
- 不删除或覆盖截图、过程文件、证据或历史报告。

多搜索词仍由外层按批次处理：每批最多 3 个词，每个词一个 Evaluation Agent，上批完成后才可继续。
