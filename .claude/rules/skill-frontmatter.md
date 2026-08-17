---
description: 编辑/新建任意 SKILL.md 时生效，强制 frontmatter 契约，保证工作流能自动发现与计分。
globs: "**/SKILL.md"
---

# SKILL.md frontmatter 契约（强制）

所有 `SKILL.md` 必须含 YAML frontmatter。按 skill 类型区分必填键：

**① eval 评测项**（路径 `phase3-*/eval-skills/eval-X-*/SKILL.md`）必须四键齐全，缺一不可（工作流靠它们自动发现与计分，缺则该 skill 不被发现或报告缺键）：

```yaml
---
name: <kebab-case 唯一名>
title: <中文名>
weight: { "优秀": <n>, "不达标": <n> }          # 两档；若该评测确需中间档，写 { "优秀":n, "达标":n, "不达标":n }
aggregate: "<聚合到 Tab 级的规则文本>"          # 评测 agent 直接读
extra: ""                                       # 非空会注入评测 prompt 并在报告标「AI 初步建议，待人工确认」徽标
description: <触发描述>
metadata: { author: ..., version: "...", domain: ... }
---
```

**② 非评测 skill**（`phase1-screenshot`、`phase2-card-annotation`、`phase4-issue-evidence`、`phase5-report` 等截图/标注/渲染 skill，不参与评级计分）只需 `name` + `description`，**不要求** `title/weight/aggregate`。

## 强制规则

- `weight` 的键只能是 `优秀` / `达标` / `不达标`，**不可**用 高线/中线/低线、A/B/C 等其他分档名。原始评级若为其他分档，必须在 skill 正文或 `aggregate` 里说明映射，输出 schema 仍是 优秀/达标/不达标。
- 两档制 skill（多数 eval-1~9 现已两档）：`weight` 写 `{ "优秀": n, "不达标": n }`，省略 `达标` 键；工作流用 `.get("达标",0)` 兜底，schema 已把 `达标` 设为可选。**不要为了凑三档而硬加 `达标` 键。**
- `aggregate` 必须写清两件事：① 该 skill 原始颗粒度（如「搜索词×组件」）如何评级；② 如何聚合到 Tab 级（取最差 / 求和 / 阈值映射）。例如两档制取最差：`任一组件不达标→该Tab不达标；全部优秀→优秀`。
- `name` 用 kebab-case，且应与所在目录名一致（如 `eval-1-supply-completeness` 与目录 `eval-1-supply-completeness/` 对应）。

## 校验

项目内置 `scripts/validate_skill_frontmatter.py`，作为 PostToolUse 钩子在每次 Edit/Write SKILL.md 后自动跑（见 `.claude/settings.json`）。它按 skill 类型区分校验：eval 评测项查 `name/title/weight/aggregate` 四键；非评测 skill 只查 `name`。打印 OK/FAIL（非阻断）。若报 FAIL，必须补齐再继续。
