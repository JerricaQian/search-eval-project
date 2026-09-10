# Evaluation workflow skill

`run-eval.md` 是面向 Agent 的执行入口，包含任务路由、确认门槛和 Phase1→5 的强制顺序；本说明面向维护者。

当前项目只有一套活动中的 Phase2→4 契约：

- Task protocol：`MEITUAN_EVAL_TASK`
- Agent contract：`workflow/contracts/phase234-query-pipeline.md`
- Result schema：`workflow/contracts/evaluation-result.schema.json`

未命名但可读取的截图属于有效输入。发现器将其放入 `unlabeledGroups`，宿主通过当前像素生成 `screenshot.identity-map`，随后按 query 创建词级任务。文件名不能成为评测阻断条件。

历史契约不在当前入口中继续维护。更新流程后运行：

```bash
python3 -m unittest discover -s tests
```

运行产物保留在本地 `.artifacts/`、`screenshots-out/` 和 `reports/`，除非用户明确授权，不应提交或上传。
