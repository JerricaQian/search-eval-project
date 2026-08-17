# page_framework-eval 维度

本维度用于「页面框架级」评测：粒度是搜索结果页的整体模块组织、视觉秩序与浏览路径，不以单一元素或单张商卡作为独立评级对象。

## 已落地评测项

- `eval-1-supply-module-completeness/` —— **供给模块完整性**。
- `eval-2-visual-order-alignment/` —— **视觉秩序与对齐**。
- `eval-3-page-color-logic/` —— **页面色彩逻辑**。
- `eval-4-static-component-complexity/` —— **静态组件复杂度**。
- `eval-5-browsing-flow-smoothness/` —— **浏览流程顺畅性**。
- `eval-6-info-comparability/` —— **信息可比性**。
- `eval-7-info-redundancy/` —— **信息冗余**。

页面框架维度的原始评级以页面/Tab 为颗粒度；是否使用统一元素清单、`overview.total` 的具体含义及聚合规则，以每项 `SKILL.md` 的 `aggregate` 和工作流注入约束为准。不得为了与单一元素维度一致而自行虚构元素计数。

## 如何新增评测项

1. 在本目录下建子目录 `eval-X-<name>/`（X 为编号，`<name>` 为英文短名）。
2. 在其中写 `SKILL.md`，frontmatter 必须声明：
   ```yaml
   ---
   name: eval-X-<name>
   title: 中文名
   weight: { "优秀": 1, "达标": 0, "不达标": -1 }
   aggregate: "聚合到 Tab 级的规则文本"
   extra: ""
   description: ...
   ---
   ```
3. 正文写该评测项的评级标准。

工作流会自动扫描本目录下所有 `eval-*` 子目录并读取 frontmatter，无需改工作流。详见顶层 `README.md` 的「eval skill frontmatter 约定」。
