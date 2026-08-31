# 美团搜索结果页标准化评测 Agent

这是一个面向美团搜索结果页的可复用评测系统。它把截图采集、页面事实识别、多维度评测、问题证据和 HTML 报告串成一条可追溯的流程。

```text
截图 → Phase2 事实清单 → Phase3 评测 → Phase4 问题证据 → Phase5 HTML 报告
```

系统将截图采集与评测分开处理：已有截图可以稍后再评测；只想采集截图时也不会生成评测结论。

## 如何发起任务

| 目标 | 可以这样说 | 交付物 |
|---|---|---|
| 评测一张已有图 | “评测这张截图：`<绝对路径>`” | 单图事实清单、评测结果、问题证据和本地 HTML 报告 |
| 评测多张图或一个目录 | “评测这个目录中的截图：`<绝对路径>`” | 先返回截图分组；确认后按组评测并生成汇总产物 |
| 截图后评测 | “搜索 `<词>`，截图 `<Tab>` 第 `<屏>` 屏后评测” | 截图通过检查后，再确认评测范围与报告出口 |
| 只截图 | “只截图，不评测：搜索 `<词>`，`<Tab>`，第 `<屏>` 屏” | 可复用截图写入 `screenshots/` |
| 复核已有报告 | “复核报告 `<路径>`” | 复核其输入、事实清单、结果和证据；必要时新建批次重跑 |
| 了解能力 | “这个项目能评什么？” | 输入、评测范围和产物说明；不会运行评测 |

系统不会把用户提供的图片直接当作人工点评对象。它会先确认任务模式、输入范围和必要参数，再进入对应流程。

## 快速开始

在项目根目录执行：

```bash
# 使用已有截图
bash setup.sh

# 需要现场截图时，额外检查设备环境
bash setup.sh --with-device
```

### 评测项目外的已有截图

先将原图以副本方式接入项目，再选择要评测的截图组：

```bash
python3 workflow/eval_cli.py prepare-evaluate \
  --project-dir "$(pwd)" \
  --source-dir "/path/to/external/screenshots"
```

该命令不修改源文件，会把图片以原文件名复制到 `screenshots/`。同名但内容不同的图片会自动保留为独立副本，不会覆盖旧文件。

若已确定搜索词，可追加 `--query <搜索词>`。命令会生成可交给宿主执行环境的任务文件；具体交接方式见 [HOST_ADAPTER.md](workflow/HOST_ADAPTER.md)。

## 三种任务模式

| 模式 | 适用场景 | 需要提供的信息 |
|---|---|---|
| `capture_only` | 只采集截图 | 搜索词、Tab、屏数 |
| `evaluate_only` | 评测已有截图 | 截图范围、评测范围、报告出口 |
| `capture_and_evaluate` | 先截图再评测 | 先提供搜索词、Tab、屏数；截图完成后再确认评测范围和报告出口 |

评测已有截图时，系统会先发现并分组 `screenshots/` 内的文件。选择文件后，搜索词、Tab 和屏号会从文件名 `<搜索词>_<Tab>_<屏>.<ext>` 推导，无需重复填写。

## 输入、输出与数据流

| 阶段 | 输入 | 主要输出 |
|---|---|---|
| Phase1 截图/发现 | 设备或已有截图 | `screenshots/` |
| Phase2 事实识别 | 单张截图 | `screenshots-out/` 内一图一份事实清单 |
| Phase3 评测 | 原始截图和对应事实清单 | `.artifacts/过程文件-评测结果与审计/` |
| Phase4 证据 | 已确认的问题定位 | `screenshots-out/evidence/` |
| Phase5 报告 | 已验收的评测结果和证据 | `reports/` 内本地 HTML；多词批次额外生成治理数据集 |

每张截图都有独立事实清单，Phase3 只消费已通过 Phase2 校验的清单。批量索引只用于定位文件，不能替代单图事实。

## 评测范围

系统提供 19 个评测项，分为三个维度：

| 维度 | 内容 | 数量 |
|---|---|---:|
| 卡片/组件 | 供给、视觉秩序、色彩、元素复杂度、信息层级、分区、真实性、冗余 | 8 |
| 单元素 | 供给质量、色彩逻辑、元素规范、信息真实性 | 4 |
| 页面框架 | 模块完整性、视觉秩序、页面色彩、静态组件复杂度、浏览流畅度、信息可比性、信息冗余 | 7 |

可以选择完整 19 项、一个或多个维度，或指定具体评测项。非完整评测会在报告中标识已选范围，不能与完整综合分直接比较。

## 工作方式

```text
Workflow
├─ Screenshot Agent：截图或发现已有截图
└─ Evaluation Agent：Phase2 → Phase3 → Phase4 → Phase5
```

Workflow 只负责按需询问、任务路由和批次控制；评分和事实判断由评测流程完成。进入评测后，事实清单、评测结果和证据都必须通过相应校验，才会生成报告。

## 目录速览

```text
phase1-screenshot/                 截图与已有截图发现
phase2-card-annotation/            单图事实识别与校验
phase3-evaluation/                Phase3 统一入口、共同知识与 19 项评测
phase4-issue-evidence/             问题证据图
phase5-report/                     本地报告与可选线上看板
workflow/                          任务路由与宿主交接
screenshots/                       截图输入
screenshots-out/                   Phase2 清单与问题证据
.artifacts/过程文件-评测结果与审计/ 过程结果与审计
reports/                           最终本地报告
```

## 深入文档

| 需要了解的内容 | 入口 |
|---|---|
| 任务模式、参数和调用顺序 | [.claude/skills/run-eval.md](.claude/skills/run-eval.md) |
| 项目阶段、数据流和执行约束 | [CLAUDE.md](CLAUDE.md) |
| 项目外截图接入与宿主交接 | [workflow/HOST_ADAPTER.md](workflow/HOST_ADAPTER.md) |
| 截图规则 | [phase1-screenshot/SKILL.md](phase1-screenshot/SKILL.md) |
| Phase2 事实清单与校验 | [phase2-card-annotation/SKILL.md](phase2-card-annotation/SKILL.md) |
| Phase3 范围、维度与 19 项 Skill | [phase3-evaluation/README.md](phase3-evaluation/README.md) |
| 本地报告与治理看板 | [phase5-report/SKILL.md](phase5-report/SKILL.md) |

## 本地产物与 Git 边界

`.artifacts/`、`screenshots-out/` 和 `reports/` 是用户本地运行产物。除非明确要求上传，不应将它们加入 Git、提交或推送。
