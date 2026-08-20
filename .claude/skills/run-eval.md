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

## 先做请求预检，再回复用户

在读取截图像素、做人工判断或调用 Workflow 前，必须完成下列动作：

1. 完整读取项目根 `CLAUDE.md`、存在时的 `AGENTS.md`、根 `README.md`；
2. 识别请求属于单图、多图/目录、现场截图、已有报告复核还是能力咨询；
3. 对评测任务读取本文件、`workflow/meituan_eval_workflow.js`，并定位所选阶段的 `SKILL.md`；
4. 先回复用户：已识别的任务类型、输入范围、下一步阶段、缺失输入和最终产物。

这一步是门禁：未完成时不得对截图打分、罗列 UI 问题，或宣称已评测。人工视觉判断只能作为流水线结束后的“人工复核”，不能代替 Phase2～5。

### 请求路由与首次回复

| 用户表达 | 路由 | 首次回复必须包含 |
|---|---|---|
| 一张图片/一个图片路径 | `evaluate_only`；先发现、校验并选择该图 | 文件路径、任务模式、待确认的维度/报告出口，以及 manifest→证据→HTML 产物 |
| 多张图片或目录 | `evaluate_only`；先发现并按搜索词、Tab、屏号分组 | 发现到的分组和无效/无法解析项；不对任何单图先行点评 |
| “帮我截图后评测” | `capture_and_evaluate` | 需要的搜索词、Tab、屏数；说明截图成功后才会确认评测配置 |
| “只帮我截图” | `capture_only` | 需要的搜索词、Tab、屏数；明确不会生成评测报告 |
| “这份报告为什么有问题” | 复核既有 Phase2～5 产物；必要时重跑受影响阶段 | 复核对象、证据/manifest 范围和新批次产物策略 |
| “你能评什么” | 只读取项目说明与技能 | 支持的输入、评测维度、产物和限制；明确尚未执行评测 |

项目外的用户图片必须以不改动原件的方式进入项目级 `screenshots/` 输入集，再按发现流程处理；不能直接根据外部路径进行手工评判。

### 项目外截图的直接复制（必经）

用户给出项目外目录时，先用可移植前置入口导入；不要要求用户手工改名，也不要将外部路径直接写入 `selectedScreenshots`：

```bash
python3 workflow/eval_cli.py prepare-evaluate \
  --project-dir <项目绝对路径> \
  --source-dir <外部截图目录>
```

该命令保留源文件，并将图片按原文件名直接复制到 `screenshots/`，不生成 Intake
manifest，也不重命名。命令输出 `MEITUAN_EVAL_HANDOFF_V1`：无 `--query` 时返回可供
用户选择的截图组；带 `--query` 时返回可传给宿主 Workflow 的 `evaluate_only` 参数。
发现阶段报告无效或无法解析的文件；同名不同字节时自动追加递增的副本序号，保留两份文件，并视为独立截图而非原截图的同一屏。

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
  "externalScreenshotDir": "<项目外截图目录>",
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
