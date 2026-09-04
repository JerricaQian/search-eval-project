# 跨 Harness 最小接入

`workflow/meituan_eval_workflow.js` 是支持其 DSL 的宿主 adapter，不是通用执行器。
Claude Code、Codex、Catpaw 或其他 Harness 都使用同一个轻量交接文件，避免复制整段
Phase2～4 prompt。

## 1. 创建不可变任务

```bash
<pythonBin> workflow/eval_cli.py prepare-evaluate \
  --project-dir "<项目绝对路径>" \
  --source-dir "<外部截图目录>" \
  --query "<已确认的搜索词>" \
  --run-id "<本词唯一 runId>" \
  --batch-id "<本批共享 batchId>"
```

`<pythonBin>` 是当前 Harness 用于启动 CLI 的解释器；它会被写入 `workflowArgs.pythonBin`。

文件名不含搜索词、Tab、屏号时仍保留原名。无 `--query` 首次运行会返回 `awaiting_visual_identity_resolution` 和候选路径；宿主必须直接读取这些当前图片像素，生成 `screenshot.identity-map`，再把映射交回 CLI。文件名不得阻断，也不得要求用户先改名：

```bash
<pythonBin> workflow/eval_cli.py prepare-evaluate \
  --project-dir "<项目绝对路径>" \
  --source-dir "<外部截图目录>" \
  --identity-map "<宿主生成的身份映射 JSON>" \
  --selected-screenshot "<项目 screenshots/ 下的未命名文件绝对路径>"
```

身份映射遵守 `workflow/screenshot-identity.schema.json`，每项必须含 `sourcePath/sha256/query/tab/screen/identitySource/confidence`，其中自动识别使用 `identitySource=current_pixels`。CLI 会核验路径属于本次导入、当前字节 SHA 一致；一个映射含多个 query 时返回 `ready_for_query_task_split`，外层按词各建一个任务。若用户已经明确确认 query，也可以继续使用 `--query` + `--selected-screenshot`，该路径不依赖文件名。

可选地通过 `--evaluation-selection` 指定评测范围；支持完整 19 项、按维度或自定义 Skill。例如：

```bash
<pythonBin> workflow/eval_cli.py prepare-evaluate \
  --project-dir "<项目绝对路径>" \
  --source-dir "<外部截图目录>" \
  --query "<已确认的搜索词>" \
  --evaluation-selection '{"mode":"custom_skills","skills":[{"dimension":"组件/卡片维度","skillId":"eval-7"}]}'
```

正式批量治理报告要求本批各词均执行完整 19 项；部分评测只交付词级可核验产物。

输出中的 `portableTask.taskPath` 是唯一要交给 Harness 的任务入口；其中已有唯一
`runId`、隔离后的 `batchId/tag/rerunId`、截图路径、契约路径和回执命令。可用
`--run-id <稳定标识>` 复现一次指定运行；已存在的 run id 会失败而不会覆盖历史产物。
`workflowArgs.pythonBin` 是创建任务时实际运行 CLI 的解释器；Harness 必须原样传入并用它
执行所有 Python 脚本，不假定项目 `.venv`、`python3` 别名或 macOS 工具存在。

## 2. Harness 只做一件事

先确认宿主实际具备读图、读文件、运行命令和写 JSON 权限。新建 `MEITUAN_EVAL_TASK` 的 `requiredCapabilities` 是强制预检；无法读取图像像素时写 `blockedAt=preflight`、`error=model_vision_not_supported`，不要派发 Phase2。

通过预检后，让一个 Evaluation Agent：

1. 读取 `<taskPath>`，再读取其中 `contractFiles`；
2. 对 `workflowArgs.query` 完整执行 Phase2 → Phase3 → Phase4；Stage D 只返回空交接对象；
3. 把最终 JSON 写到 `resultPath`，不把长契约复制进新的子 Agent prompt；
4. 执行 task 中的 `completionCommand`。

若 Harness 能执行 Workflow DSL，可直接把 `workflowArgs` 传给
`workflow/meituan_eval_workflow.js`，并将返回对象中的 `evaluationResult` 写到 `resultPath` 后执行
同一条 completion command。

## 3. 只认可本地回执

`finalize-evaluate` 会拒绝：缺失 Stage A～D、`ok=true` 但 Phase2～4 产物不完整、审计 JSON
不是 `valid=true`、空文件、项目外路径或重复的成功写入。成功时创建一次性的
`runs/<runId>/receipt.json`；阻断结果也会有可追溯回执。若同一任务在完成返工后由
`blocked` 变为 `completed`，工具会将旧回执保留为 `receipt.blocked-<stage>.json`，再写入
新的成功回执；已完成回执绝不覆盖。

这层不做 OCR 或视觉判断。批次重试由 `prepare-batch`、`advance-batch` 和 `create-batch-retry` 保存为追加式状态快照；每次重试都有新的 `runId/taskPath`，不会覆盖失败产物。

若评测完成后需要规范名称，运行 `workflow/materialize_screenshot_aliases.py`，同时传入 completed `receipt.json`，把身份映射物化为独立规范副本和 `screenshot.canonical-alias-map`。脚本在没有完成回执时拒绝运行，且永不移动、覆盖或删除原始 `IMG_*.PNG`；Tab/屏号仍不确定的条目保持原名并记录 skipped，不猜写。

## 4. 全部词终态后统一生成 Phase5

先用 `prepare-batch` 冻结所有预期 task。每批最多并发 3 个词级 Evaluation Agent；每轮结束用 `advance-batch` 核验回执。失败词通过 `create-batch-retry` 生成新的隔离任务并交给新的 Evaluation Agent，最多三次；第三次仍失败标记 abandoned。所有词进入 completed/abandoned 后执行一次：

```bash
<pythonBin> workflow/eval_cli.py finalize-batch \
  --project-dir "<项目绝对路径>" \
  --batch-id "<本批共享 batchId>" \
  --batch-state "<advance-batch 返回的最新 statePath>" \
  --expected-business-tabs "<逗号分隔 businessCode>"
```

该命令重新核验每份最终契约结果及本地回执，只把 completed 回执中的精确 manifest 和评测结果交给确定性生成器，生成一份批量 HTML 与一份治理数据集。abandoned 词仅保留在批次状态中，不进入报告；尚未终态会阻断，全部 abandoned 也不会生成空报告。
