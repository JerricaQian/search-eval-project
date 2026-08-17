# phase2-card-annotation

用于 IMD 搜索结果页/信息页的「宏观组件 + 商卡内部分区」两级可视化标注技能（原名 `imd-card-annotation`，已随目录更名）。

支持两条产出路径：

1. **IMD 在线标注**：通过 `window.mg` 插件 API，在设计文件中非破坏性新增半透明矩形与红色文字标签。
2. **本地截图标注**：在 PNG/JPG 上直接绘制相同语义、配色与任务结构的标注图。

技能入口为 `SKILL.md`，识别标准为 `references/页面与商卡识别规则.md`。本目录采用标准 Agent Skill 结构：根目录 `SKILL.md` 含 YAML frontmatter，`scripts/` 存放确定性工具，`references/` 存放按需读取的规则，`scenes/` 存放可审计的场景真值数据。

## 目录结构

```text
phase2-card-annotation/
├── SKILL.md                              # 触发描述、工作流、规则与防错机制
├── README.md                             # 本文件
├── references/
│   └── 页面与商卡识别规则.md              # 宏观组件、卡片类型、字段与判定规则
├── scenes/
│   └── scene_spec.template.json          # 声明式场景任务表模板（不含可复用坐标）
├── scripts/
│   ├── annotation_scene.py               # 通用 SceneSpec 校验、渲染与审计执行器
│   ├── annotate_image.py                 # 本地 PNG/JPG 渲染内核（Pillow）
│   ├── scan_rows.py                      # 留白带/内容行候选边界发现器
│   ├── detect_photo_region.py            # 照片区域候选发现器（仅辅助）
│   ├── imd_annotate_api.py               # IMD 插件 API 标注内核
│   ├── imd_eval.py / imd_export_node.py  # IMD 浏览器表达式与画板导出工具
│   ├── imd_verify_export.py              # IMD 标注导出验证工具
│   └── annotate_<场景>.py                # 已验证截图的场景真值脚本，非新图模板
├── screenshots/                          # 场景脚本自带的原始本地截图（历史）
└── out/                                  # 场景脚本的标注 PNG 与审计报告（历史）
```

> **工作流级输入/输出**（由 `workflow/meituan_eval_workflow.js` 驱动时）：截图取自项目根 `screenshots/`，标注产物（标注图 + 统一元素清单 JSON）写入项目根 `screenshots-out/`，供 phase3 评测参考图文。本目录内的 `screenshots/`、`out/` 仅用于场景脚本独立运行，工作流不以此为准。详见项目根 `CLAUDE.md` / `README.md`。

## 技能规范与依赖

- 本仓库根目录即 Skill 根目录；安装时应保证目标目录下直接存在 `SKILL.md`、`scripts/`、`references/` 与 `scenes/`。
- `SKILL.md` 的 YAML frontmatter 声明了 `name` 与触发描述；可安装到全局 Skill 目录或项目级 Skill 目录。
- 本地标注依赖：Python 3、Pillow、numpy。
- 在线 IMD 标注额外依赖：`catdesk` 与有效的 IMD 登录态。
- 运行前优先阅读 `SKILL.md` 的「核心原则」「绘制前的强制语义-几何核对」「子代理耗时基线与超时介入」和「踩坑速查」。

## 核心原则

1. **内容优先，扫描辅助**：`scan_rows.py` 只提供卡间、模块间或文本行的候选边界；它不能决定标题、价格、标签、下挂、营销横幅等业务语义。
2. **逐图、逐卡独立确认**：不能跨截图复用绝对坐标，也不能将首卡坐标平移给后续卡。每张卡都要独立确认头图四边、文字列和实际信息行。
3. **先锁列，再分行**：左图右文卡先确认图片列和文本列；标题、标签、价格、文字下挂默认不得压到头图区。
4. **真实模块才标**：图筛必须完整覆盖图片/图标行和文字行；快筛必须是实际的纯文字筛选行；营销横幅必须有明确促销/权益文案。
5. **第二、第三屏默认是续页**：除非原图明确存在完整组件，否则不得沿用首屏的 `Tab` 或 `图筛`。
6. **异构卡不套商卡模板**：`大家还在搜` 标为 `相似推荐提示`；费力度/满意度/调研解释及运营聚合内容标为 `运营聚合卡`；不得为它们创建普通商卡分区。
7. **反向审图是交付的一部分**：导出后必须对照原图检查宏观模块、卡边界、头图四边、文本列、标签/下挂切割和不存在的组件。

## 通用脚本：SceneSpec 执行器

历史 `annotate_<场景>.py` 脚本保留的是各自截图经审图确认后的**场景真值**。它们可用于复查该同一张图，但不能用作新截图的坐标模板。

新增 `scripts/annotation_scene.py` 将可复用的部分收敛为统一执行器：

- 稳定任务协议：`label/x/y/w/h/kind`；
- 输入图片尺寸与声明画布校验；
- 非空、唯一任务 ID、正尺寸、越界检查；
- 卡级 `parent` 关联的结构告警；
- 输出 PNG 与机器可读的审计报告；
- 保持 `annotate_image.py` 的统一配色与绘制顺序。

它**不做自动语义识别**、不根据旧脚本推断坐标、不自动把扫描行绑定为区域类型。当前截图的任务真值必须先按原图与规则确认。

### 1. 创建当前截图的 SceneSpec

复制 `scenes/scene_spec.template.json`，按当前截图填写。每个区域都应包含唯一 `id`、显示用 `label`、像素框、`kind`；推荐额外保留 `parent`、`semantic_role`、`source`、`cropped`，方便审计。

```json
{
  "scene_id": "2_example_1",
  "input": "../screenshots/2/示例_全部_1.png",
  "output": "../out/2/示例_全部_1_annotated.png",
  "canvas": {"width": 1224, "height": 2700},
  "coordinate_space": "image_pixel",
  "annotations": [
    {
      "id": "card-01-border",
      "label": "商卡1_border",
      "x": 18,
      "y": 800,
      "w": 1188,
      "h": 420,
      "kind": "border",
      "semantic_role": "merchant_card",
      "source": "manual+scan_rows"
    }
  ]
}
```

### 2. 先做几何校验

```bash
python3 scripts/annotation_scene.py scenes/<scene>.json --dry-run
```

### 3. 渲染并生成审计报告

```bash
python3 scripts/annotation_scene.py scenes/<scene>.json
```

会生成：

- `out/.../<scene>_annotated.png`
- `out/.../<scene>_annotated.report.json`

报告记录图片尺寸、任务数、层级统计、截断任务数、异构任务数、最终任务表及结构告警。越界、重复 ID、声明画布不符、非法 `kind` 会阻断导出。

## 推荐本地标注流程

1. 清点用户指定的截图文件，确保输入、输出和任务表一一对应。
2. 同一张图的同一扫描目的与同一参数组合最多执行一次：允许一次整图 `scan_rows.py`；需要时，对每张**当前卡已确认的文本列**各执行一次限区扫描。扫描只辅助边界，不能决定区域语义。
3. 读取当前原图，先判定顶部组件、营销/运营模块、标准商卡、异构卡和截断范围。
4. 对每张标准卡记录：卡类型、实际标题、头图四边、文本列范围、信息行文案、标签/下挂形态。
5. 填写当前截图的 SceneSpec 或场景脚本，运行 `annotation_scene.py` / `annotate_image.py`。
6. 读取输出图，与原图按「宏观模块 → 卡边界 → 头图 → 文本列 → 标签/下挂 → 异构卡 → 不存在组件」反向核对；有误则修改当前任务表后重绘。

## 并行子代理与耗时控制

多图任务可按“每张截图或每组同场景截图”并行分配给子代理，避免主线程重复读取大图。每个子代理必须完整交付：单次扫描、原图识别、任务表、PNG、反向审图。

主代理记录 `dispatch_at`、`complete_at`、`image_count` 与 `elapsed_per_image`，用于观察异常和评估执行器效果。

固定以子代理派发后 **11 分钟未完成** 作为介入节点，不再计算或使用 `T_avg` 改变阈值。介入时检查已完成步骤、SceneSpec、脚本、输出、审计报告和终端状态；排除重复扫描、反复读图、模板化补全或过度拆分后，要求其收敛、接管或拆为单图任务。详见 `SKILL.md`。

## 在线 IMD 标注

在线流程仍使用 `imd_annotate_api.py`、`imd_export_node.py` 与 `imd_verify_export.py`：导出画板底图 → 按当前画板内容识别任务 → 新增 `[ANNO]` / `[ANNO-TXT]` 图层 → 克隆导出验证。在线标注只新增标注图层，不移动、修改或删除原始设计图层。

完整工作流、配色表、卡型字段与所有踩坑项以 `SKILL.md` 和 `references/页面与商卡识别规则.md` 为准。
