# Search Evaluation Agent entry contract

This repository is a workflow-driven Meituan search-result evaluation agent.
Do not turn a request for screenshot evaluation into an ad-hoc visual review.

## Mandatory route

For any request involving search screenshots, evaluation, existing reports, batch
governance, or agent capabilities:

1. Read `CLAUDE.md`, `README.md`, and `.claude/skills/run-eval.md` before
   inspecting screenshot pixels or issuing a rating.
2. Classify the request as `capture_only`, `evaluate_only`,
   `capture_and_evaluate`, report review, or capability consultation.
3. For an external screenshot path or directory, copy image files directly to
   `screenshots/` with their original filenames. Preserve source files; only
   the project copy may enter discovery and evaluation. If a same-named target
   has different bytes, append an incrementing copy suffix instead of
   overwriting or blocking. A suffixed filename is a distinct screenshot and
   must not be merged with the unsuffixed file during discovery.
4. Use `phase1-screenshot/scripts/discover_screenshot_groups.py` on `screenshots/`, return the
   canonical groups, valid unnamed candidates, and truly invalid inputs. Valid
   unnamed screenshots must proceed through current-pixel identity mapping and
   must never be blocked as unparseable. Then obtain only the minimum evaluation
   configuration required by the selected mode.
5. Only after the preceding steps may each query Evaluation Agent run Phase2 → Phase4.
   Phase5 runs once after every expected query is terminal: either it has a
   completed local receipt, or it has failed three isolated Evaluation Agent
   attempts and is explicitly marked abandoned. Phase5 consumes only completed
   queries and does not mention abandoned queries in the report; if all queries
   are abandoned, do not generate an empty Phase5 report.
   Human visual comments are permitted solely as clearly-labelled post-pipeline
   review and never replace the formal result.

## Portable front door

When a host cannot execute `workflow/meituan_eval_workflow.js` directly, use
`python3 workflow/eval_cli.py prepare-evaluate` to run the copy and discovery
preflight. For unnamed images the host first reads current pixels and supplies a
SHA-bound `screenshot.identity-map`; filenames never block evaluation. When a
query is selected it emits a `MEITUAN_EVAL_TASK` portable
task with a unique `runId`; queries in one report share a `batchId`. Give the
host only each `taskPath`, run its completion command, then use
`finalize-batch` once all expected receipts are completed. See
`workflow/HOST_ADAPTER.md`. The CLI does not claim to execute the
LLM-dependent Phase3 judgement.

## Local artifact publication policy

`.artifacts/`, `screenshots-out/`, and `reports/` are user-local run outputs.
Do not add, commit, force-add, push, or otherwise publish files from these
directories to Git unless the user explicitly requests that upload. A request
to run an evaluation, generate evidence, or build a report is not upload
authorization.

## Golden-contract version drift

今后遇到这类“契约/哈希版本不一致、但原始事实可能仍有效”的阻断，默认不改原件，先验证兼容性，再创建带新版本号的完整副本进行修复与复验。
