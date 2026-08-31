# Phase3 评测

Phase3 把 19 项评测组织为一个入口、三个维度。评测官负责范围解析与事实边界，真正的评分规则仍由各叶子 `SKILL.md` 定义。

```text
phase3-evaluation/
├── SKILL.md                         统一执行入口
├── catalog.json                     维度 ID、目录和 Skill 顺序的唯一映射
├── common/                          三个维度共享的知识、路由与测量能力
└── dimensions/
    ├── single-element/              4 项单一元素评测
    ├── card-component/              8 项组件/卡片评测
    └── page-framework/              7 项页面框架评测
```

## 三层职责

| 层级 | 负责什么 | 不负责什么 |
|---|---|---|
| 统一入口 | 解析 `full_19`、维度或自定义 Skill；加载共同知识；传递覆盖范围 | 不新增第 20 个评分项 |
| 维度契约 | 定义评测单位、事实输入、证据和聚合的共用边界 | 不覆盖叶子 Skill 的专属阈值 |
| 叶子 Skill | 定义具体对象、测量、判定、权重和聚合 | 不越界评价其他层级 |

## 固定外部 ID

以下 ID 已写入结果、校验器和报告契约，因此保持稳定；目录改名不改变输出：

- `phase3-single_element-eval`
- `phase3-card_or_component-eval`
- `phase3-page_framework-eval`

所有代码通过 [`catalog.json`](catalog.json) 解析这些 ID，不应再用 ID 拼接物理目录。

## 共享与专属脚本

- `common/routing/`：选择解析，只决定“运行哪些 Skill”。
- `common/scripts/`：多个维度共同使用的裁剪、颜色分类和范围处理。
- `dimensions/<dimension>/scripts/`：一个维度内多个 Skill 共享的确定性辅助器。
- `dimensions/<dimension>/skills/<skill>/scripts/`：只服务一个 Skill 的测量脚本。

新增或移动 Skill 时，先改 `catalog.json`，再运行范围解析和契约测试；不要新增另一份维度路径映射。
