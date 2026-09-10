---
name: phase234-query-pipeline
description: Claude 兼容入口；转交宿主中立的单搜索词 Phase2→Phase3→Phase4 契约。
---

# Claude 兼容适配层

本文件只保留 Claude 按名称加载的兼容入口。正式、宿主中立的执行契约位于：

```text
workflow/contracts/phase234-query-pipeline.md
```

收到 `MEITUAN_EVAL_TASK` 后，必须完整读取上述正式契约，并以 task 中的
`contractFiles`、`requiredReads`、`evalTargets`、`resultPath` 和
`completionCommand` 为准。不得在本适配层复制或改写 Phase2～4 业务规则。
