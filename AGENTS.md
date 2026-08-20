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
4. Use `scripts/discover_screenshot_groups.py` on `screenshots/`, return the
   discovered groups and invalid/unparseable inputs, then obtain the minimum
   evaluation configuration required by the selected mode.
5. Only after the preceding steps may the Evaluation Agent run Phase2 → Phase5.
   Human visual comments are permitted solely as clearly-labelled post-pipeline
   review and never replace the formal result.

## Portable front door

When a host cannot execute `workflow/meituan_eval_workflow.js` directly, use
`python3 workflow/eval_cli.py prepare-evaluate` to run the copy and discovery
preflight and emit a `MEITUAN_EVAL_HANDOFF_V1` request for that host's workflow
adapter. The CLI does not claim to execute the LLM-dependent Phase3 judgement.
