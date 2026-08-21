# 跨 Harness 最小接入

`workflow/meituan_eval_workflow.js` 是支持其 DSL 的宿主 adapter，不是通用执行器。
Claude Code、Codex、Catpaw 或其他 Harness 都使用同一个轻量交接文件，避免复制整段
Phase2～5 prompt。

## 1. 创建不可变任务

```bash
python3 workflow/eval_cli.py prepare-evaluate \
  --project-dir "<项目绝对路径>" \
  --source-dir "<外部截图目录>" \
  --query "<已确认的搜索词>"
```

输出中的 `portableTask.taskPath` 是唯一要交给 Harness 的任务入口；其中已有唯一
`runId`、隔离后的 `batchId/tag/rerunId`、截图路径、契约路径和回执命令。可用
`--run-id <稳定标识>` 复现一次指定运行；已存在的 run id 会失败而不会覆盖历史产物。

## 2. Harness 只做一件事

让一个具备读图、读文件、运行命令和写 JSON 权限的 Evaluation Agent：

1. 读取 `<taskPath>`，再读取其中 `contractFiles`；
2. 对 `workflowArgs.query` 完整执行 Stage A → D；
3. 把最终 JSON 写到 `resultPath`，不把长契约复制进新的子 Agent prompt；
4. 执行 task 中的 `completionCommand`。

若 Harness 能执行 Workflow DSL，可直接把 `workflowArgs` 传给
`workflow/meituan_eval_workflow.js`，并将其 Stage A～D 返回值写到 `resultPath` 后执行
同一条 completion command。

## 3. 只认可本地回执

`finalize-evaluate` 会拒绝：缺失 Stage A～D、`ok=true` 但产物不完整、审计 JSON
不是 `valid=true`、空文件、项目外路径或重复写入。成功时创建一次性的
`runs/<runId>/receipt.json`；阻断结果也会有可追溯回执。

这层不做 OCR、视觉判断或重试策略，因此不会引入新的评测逻辑或额外 token 开销。
