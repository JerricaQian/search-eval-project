# single_element-eval 维度

本维度用于「单一元素级」评测：粒度是单个 UI 元素（标题、每个独立标签、价格、评分、按钮、提示条等），
逐元素给出评级，而非组件级或页面级。

## 已落地评测项

- `eval-1-supply-quality-scanner/` —— **供给呈现质量（单一元素）**。逐元素判断图片/文字是否属低质量供给。
  图片查合规/完整性/画质/比例/相关性；文字查完整性/准确性/用户视角/相关性。二档制（优秀/不达标，无达标档）。
- `eval-2-color-logic-single-element/` —— **色彩运用有逻辑（指标 1.2.2，单一元素维度）**。
  统计单一元素内的总颜色数量（36 色标准，底色/文字色/icon 均计入，渐变按跨越色阶数计），
  阈值 ≤2 优秀🟢 / =3 达标🟡 / >3 不达标🔴（三档制）。含 `scripts/count_element_colors.py` 与 `references/36色标准.md`。
- `eval-3-element-compliance-scanner/` —— **静态元素符合规范（单一元素）**。逐元素比对美团设计规范
  （分区规范/原子样式/组件源字典），判位置/字号/颜色语义/标签样式/收敛规则是否合规。二档制。
- `eval-4-info-authenticity-single-element/` —— **信息与功能真实无歧义（单一元素）**。
  逐元素判断文案/图标是否存在歧义或虚假/误导。二档制（无中间档）。

## ⚠️ 统一元素口径（关键约定，2026-07-20 沉淀）

**问题背景**：同一张截图，不同评测 skill 各自拆分元素，导致元素总数不一致（曾出现 14 vs 12、49/50/51/51 的偏差），无法横向对比。

**解决机制**：评测前先跑 `phase2-card-annotation` 产出一份**统一页面元素清单 JSON**（单一事实源），所有评测 skill 必须基于该清单计数和评级，不得自行重新拆分或增删元素。

- 清单路径：`<annotatedDir>/elements_<query>.json`，默认即项目根 `screenshots-out/elements_<query>.json`；不得使用已废弃的 `screenshots/annotated/` 或 skill 内部输出目录。
- 清单结构：`{query, tab, cards:[{cardId, 卡片类型, regions:[{分区, elements:[{id, 所属组件, 元素类型, 内容, 坐标, isExcluded}]}]}]}`
- `isExcluded=true` 的元素（商家头图/营销大图/金刚icon等）不计入总数也不评测。
- **元素总数 total 由确定性脚本计算**，禁止人工推导：
  ```bash
  python3 -c "import json;d=json.load(open('elements_烧烤.json'));t=0;[t:=t+1 for c in d.get('cards',[]) for r in c.get('regions',[]) for e in r.get('elements',[]) if not e.get('isExcluded')];print('TOTAL=',t)"
  ```
- 工作流会把清单路径和计数脚本注入每个评测 agent 的 prompt，要求 `overview.total` 必须等于脚本输出。
- 各 skill 的 SKILL.md `Step 5 输出结果` 已统一为：5a 问题元素明细 / 5b 评测总览 / 5c 问题维度分布 / 5d 总结（颜色/规范项额外有排除清单），确保产出结构一致。

## frontmatter 约定（新增评测项必读）

每个 `eval-X-<name>/SKILL.md` 的 frontmatter 必须声明 `title` / `weight` / `aggregate` / `extra`：

```yaml
---
name: eval-X-<name>
title: 中文名
weight: { "优秀": 1, "达标": 0, "不达标": -1 }   # 二档项可省略「达标」键
aggregate: "聚合到 Tab 级的规则文本"
extra: ""
description: ...
---
```

- **二档制 skill（只有优秀/不达标）**：`weight` 可写 `{ "优秀": 1, "不达标": -1 }`，**「达标」键可省略**。工作流发现脚本会用 `.get("达标",0)` 兜底，schema 也已把「达标」设为可选。不要为了凑三档硬加「达标」键。
- **三档制 skill**：`weight` 三键齐全 `{ "优秀":1, "达标":0, "不达标":-1 }`。
- `aggregate`：把元素级评级聚合到 Tab 级的规则（评测 agent 直接读）。单一元素维度通常「取最差元素」。
- `extra`：可空。非空内容会作为额外说明注入评测 prompt。

## 如何新增评测项

1. 在本目录下建子目录 `eval-X-<name>/`（X 为编号，`<name>` 为英文短名）。
2. 写 `SKILL.md`：frontmatter 按上述约定；正文 `Step 5 输出结果` 遵循统一结构（5a/5b/5c/5d + Step 6 自检）。
3. 如需脚本/参考资料，放同目录 `scripts/`、`references/` 下，正文用相对路径引用。
4. 评测粒度必须是「单一元素」——逐元素判定，不要以商卡/组件为单位笼统打分。

工作流会自动扫描本目录下所有 `eval-*` 子目录并读取 frontmatter，无需改工作流。详见顶层 `README.md` 的「eval skill frontmatter 约定」。
