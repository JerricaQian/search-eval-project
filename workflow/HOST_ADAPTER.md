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

让一个具备读图、读文件、运行命令和写 JSON 权限的 Evaluation Agent：

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

这层不做 OCR、视觉判断或重试策略，因此不会引入新的评测逻辑或额外 token 开销。

## 4. 全部词完成后统一生成 Phase5

每批最多并发 3 个词级 Evaluation Agent，并等待本批全部任务得到 completed 回执。任一词阻断时只重试该词，不生成不完整报告。全部成功后执行一次：

```bash
<pythonBin> workflow/eval_cli.py finalize-batch \
  --project-dir "<项目绝对路径>" \
  --batch-id "<本批共享 batchId>" \
  --task "<query-1 taskPath>" \
  --task "<query-2 taskPath>" \
  --expected-business-tabs "<逗号分隔 businessCode>"
```

该命令重新核验每份 V3 结果及本地回执，把回执中的精确 manifest、评测结果和预期搜索词交给 `phase5-report/SKILL.md` 的确定性生成器，只生成一份批量 HTML 与一份治理数据集。它不调用模型，也不把总报告写回词级回执。
