---
description: 编辑工作流脚本/路径/目录相关文件时生效，强制命名与路径规范，防止回退到旧名/旧路径。
globs: "**/*.js", "**/*.sh", "**/*.py", "**/*.json", "**/*.md"
---

# 项目命名与路径规范（强制）

## 阶段目录命名：phaseN-<role>

五个阶段目录一律 `phaseN-<role>` 前缀，**不带 `-skill` 后缀**：

| 阶段 | 目录（已定稿） | 旧名（已废弃，不得再用） |
|---|---|---|
| phase1 截图 | `phase1-screenshot/` | screenshot-skill |
| phase2 轻量识别 | `phase2-card-annotation/` | imd-card-annotation |
| phase3 评测 | `phase3-card_or_component-eval/` `phase3-single_element-eval/` `phase3-page_framework-eval/` | card_or_component-eval（无 phase3 前缀） |
| phase4 问题证据 | `phase4-issue-evidence/` | — |
| phase5 报告 | `phase5-report/` | report-skill |

- 工作流参数：`shotSkillDir`→`phase1-screenshot`、`imdSkillDir`→`phase2-card-annotation`、`issueEvidenceSkillDir`→`phase4-issue-evidence`、`reportSkillDir`→`phase5-report`、`dimensions` 默认 `["phase3-card_or_component-eval"]`。改这些默认值时必须同步改目录或反向。
- 文档/脚本里若仍见旧名 `imd-card-annotation` / `screenshot-skill` / `report-skill` / 非前缀维度名，一律视为待替换的陈旧引用，应改为新名（重命名声明行"原 imd-card-annotation，已更名"例外，保留）。

## 数据流路径：screenshots/ → screenshots-out/ → .artifacts/ → screenshots-out/evidence/ → reports/

- phase1 截图产物 / phase2 输入：项目根 `screenshots/`
- phase2 产物（每张截图一个独立元素清单 JSON）：项目根 `screenshots-out/`（**不是** `screenshots/annotated/`，也**不是** skill 内部 `out/`）
- phase3 原始结果与审计：项目根 `.artifacts/过程文件-评测结果与审计/`
- phase4 局部问题证据：项目根 `screenshots-out/evidence/`
- phase5 报告：项目根 `reports/`
- 工作流参数：`screenshotDir`→`screenshots`、`annotatedDir`→`screenshots-out`、`reportDir`→`reports`。

## 历史场景脚本路径（非生产）

旧 SceneSpec/IMD/标注图脚本只保留历史复现能力，不得成为新截图生产入口。生产入口固定为 `run_phase2_recognition.py`，输入项目根 `screenshots/<query>_<tab>_<screen>.png`，输出 `screenshots-out/elements_<截图文件名>.json`。项目路径必须从 `projectDir` 推导，不得写死某台机器的桌面路径。

## 评级分档

- 多数 eval skill 已收敛为两档（优秀/不达标）；少数保留三档。两种都合法，由 `weight` frontmatter 声明，工作流 schema 兼容。
- 新增评测项默认两档（`{ "优秀": n, "不达标": n }`），除非确需中间档。
