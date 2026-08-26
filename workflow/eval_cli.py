#!/usr/bin/env python3
"""Portable preflight and completion guard for search evaluation runs.

The JS workflow is a host DSL.  This CLI owns the small, host-neutral boundary:
copy/discovery, an immutable task file with a unique run id, and final artifact
verification.  It deliberately does not perform the LLM judgement itself.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
HANDOFF_PROTOCOL = "MEITUAN_EVAL_HANDOFF_V1"
TASK_PROTOCOL = "MEITUAN_EVAL_TASK_V2"
RUN_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
STAGES = ("stageA", "stageB", "stageC", "stageD")


def load_module(relative_path: str, module_name: str) -> Any:
    path = PROJECT_DIR / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot_load:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


DISCOVERY = load_module("phase1-screenshot/scripts/discover_screenshot_groups.py", "search_eval_discovery")
COPY = load_module("phase1-screenshot/scripts/ingest_external_screenshots.py", "search_eval_copy")


def emit(payload: dict[str, Any], exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def valid_run_id(value: str) -> bool:
    return 1 <= len(value) <= 80 and value[0].isalnum() and all(char in RUN_ID_CHARS for char in value)


def parse_evaluation_selection(value: str) -> dict[str, Any] | None:
    """Parse the optional user-facing Phase3 selection without judging it.

    Exact dimension/Skill validation belongs to ``resolve_eval_targets.py`` in
    the workflow, because that script reads the current catalog once and is
    shared by both host paths.
    """
    if not value:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("evaluation_selection_must_be_json_object")
    return parsed


def write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"refuse_to_overwrite:{path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def archive_blocked_receipt_for_completion(receipt_path: Path, verified: dict[str, Any]) -> None:
    """Preserve a prior blocked receipt when the same task later completes.

    A blocked Evaluation Agent result is a terminal result for that attempt,
    but it must not prevent a controlled retry of the exact same portable task.
    Only the one-way ``blocked -> completed`` transition is allowed here; a
    completed delivery remains immutable.
    """
    if not receipt_path.exists() or verified.get("status") != "completed":
        return
    previous = read_json(receipt_path)
    if not isinstance(previous, dict) or previous.get("status") != "blocked":
        return
    stage = str(previous.get("blockedAt") or "unknown")
    candidate = receipt_path.with_name(f"receipt.blocked-{stage}.json")
    index = 2
    while candidate.exists():
        candidate = receipt_path.with_name(f"receipt.blocked-{stage}-{index}.json")
        index += 1
    receipt_path.replace(candidate)


def portable_task(project_dir: Path, workflow_args: dict[str, Any], run_id: str, runs_dir: Path) -> dict[str, Any]:
    run_dir = runs_dir / run_id
    if run_dir.exists():
        raise ValueError(f"run_id_already_exists:{run_dir}")
    run_dir.mkdir(parents=True)
    task_path = run_dir / "task.json"
    result_path = run_dir / "agent-result.json"
    task = {
        "protocol": TASK_PROTOCOL,
        "runId": run_id,
        "projectDir": str(project_dir),
        "workflowArgs": workflow_args,
        "contractFiles": [
            str(project_dir / ".claude/agents/phase2345-query-pipeline.md"),
            str(project_dir / ".claude/contracts/evaluation-result.schema.json"),
        ],
        "resultPath": str(result_path),
        "completionCommand": [
            sys.executable,
            str(PROJECT_DIR / "workflow/eval_cli.py"),
            "finalize-evaluate",
            "--task",
            str(task_path),
            "--result",
            str(result_path),
        ],
        "hostInstructions": [
            "Read the listed contract files from disk; do not paste them into another prompt.",
            "Run exactly one Evaluation Agent for this query and write its final Stage A-D JSON to resultPath.",
            "Run completionCommand. Only its completed receipt is a successful delivery.",
        ],
    }
    write_once(task_path, task)
    return {
        "protocol": TASK_PROTOCOL,
        "runId": run_id,
        "taskPath": str(task_path),
        "resultPath": str(result_path),
        "completionCommand": task["completionCommand"],
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def project_file(value: Any, project_dir: Path, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}:missing_path")
    path = Path(value).resolve()
    try:
        path.relative_to(project_dir)
    except ValueError as exc:
        raise ValueError(f"{label}:outside_project:{path}") from exc
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{label}:missing_or_empty:{path}")
    return str(path)


def valid_audit(value: Any, project_dir: Path, label: str) -> str:
    path = Path(project_file(value, project_dir, label))
    try:
        audit = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}:invalid_json:{path}") from exc
    if not isinstance(audit, dict) or audit.get("valid") is not True:
        raise ValueError(f"{label}:valid_not_true:{path}")
    return str(path)


def nonempty_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label}:missing_or_empty")
    return value


def validate_completed_result(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    project_dir = Path(str(task["projectDir"])).resolve()
    expected = task["workflowArgs"]
    if result.get("ok") is not True:
        blocked_at = result.get("blockedAt")
        if blocked_at not in STAGES or not isinstance(result.get("error"), str) or not result["error"].strip():
            raise ValueError("blocked_result_missing_stage_or_error")
        return {"status": "blocked", "blockedAt": blocked_at, "error": result["error"]}
    if result.get("query") != expected.get("query"):
        raise ValueError("result_query_mismatch")

    stage_a = result.get("stageA")
    stage_b = result.get("stageB")
    stage_c = result.get("stageC")
    stage_d = result.get("stageD")
    if not all(isinstance(stage, dict) for stage in (stage_a, stage_b, stage_c, stage_d)):
        raise ValueError("successful_result_missing_stage")

    manifests = nonempty_list(stage_a.get("elementListPaths"), "stageA.elementListPaths")
    audits = nonempty_list(stage_a.get("elementAuditPaths"), "stageA.elementAuditPaths")
    if len(manifests) != len(audits):
        raise ValueError("stageA.manifest_audit_count_mismatch")
    manifest_paths = [project_file(value, project_dir, "stageA.manifest") for value in manifests]
    audit_paths = [valid_audit(value, project_dir, "stageA.audit") for value in audits]
    eval_result = project_file(stage_b.get("evalResultFile"), project_dir, "stageB.evalResultFile")
    eval_audit = valid_audit(stage_b.get("evalAuditFile"), project_dir, "stageB.evalAuditFile")
    evidence = stage_c.get("evidenceImages")
    if not isinstance(evidence, list):
        raise ValueError("stageC.evidenceImages:not_a_list")
    evidence_paths = [project_file(value, project_dir, "stageC.evidenceImage") for value in evidence]
    report_path = project_file(stage_d.get("reportPath"), project_dir, "stageD.reportPath")
    return {
        "status": "completed",
        "artifacts": {
            "manifests": manifest_paths,
            "manifestAudits": audit_paths,
            "evalResult": eval_result,
            "evalAudit": eval_audit,
            "evidenceImages": evidence_paths,
            "report": report_path,
        },
    }


def command_discover(args: argparse.Namespace) -> int:
    return emit(DISCOVERY.discover(args.screenshot_dir, args.min_bytes))


def command_copy(args: argparse.Namespace) -> int:
    result = COPY.ingest(
        args.source_dir,
        args.screenshot_dir,
        dry_run=args.dry_run,
    )
    return emit(result, 0 if not result["error"] else 2)


def command_prepare(args: argparse.Namespace) -> int:
    screenshot_dir = args.screenshot_dir or args.project_dir / "screenshots"
    copied = COPY.ingest(
        args.source_dir,
        screenshot_dir,
        dry_run=args.dry_run,
    )
    discovery = DISCOVERY.discover(screenshot_dir, args.min_bytes)
    payload: dict[str, Any] = {
        "protocol": HANDOFF_PROTOCOL,
        "projectDir": str(args.project_dir.resolve()),
        "copy": copied,
        "discovery": discovery,
        "status": "copy_blocked" if copied["error"] else "awaiting_screenshot_selection",
    }
    try:
        evaluation_selection = parse_evaluation_selection(args.evaluation_selection)
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        return emit({**payload, "status": "invalid_evaluation_selection", "error": str(exc)}, 2)
    if not copied["error"] and args.query:
        copied_paths = {
            item.get("destinationPath")
            for item in copied.get("copied", []) + copied.get("alreadyPresent", []) + copied.get("renamed", [])
            if isinstance(item, dict) and isinstance(item.get("destinationPath"), str)
        }
        group = next(
            (
                item for item in discovery["groups"]
                if item["query"] == args.query and copied_paths.intersection(item.get("files", []))
            ),
            None,
        )
        if group is None:
            payload["status"] = "query_not_found_after_copy"
        else:
            run_id = args.run_id or uuid.uuid4().hex
            if not valid_run_id(run_id):
                return emit({**payload, "status": "invalid_run_id", "error": "run_id_must_be_1_to_80_alnum_dot_underscore_dash"}, 2)
            project_dir = args.project_dir.resolve()
            workflow_args = {
                "mode": "evaluate_only",
                "projectDir": str(project_dir),
                "pythonBin": sys.executable,
                "query": args.query,
                "selectedScreenshots": group["files"],
                "dimensions": args.dimensions,
                "reportOutlet": args.report_outlet,
                "phase2Mode": "lightweight",
                "runId": run_id,
                "batchId": run_id,
                "tag": run_id,
                "rerunId": run_id,
            }
            if evaluation_selection is not None:
                workflow_args["evaluationSelection"] = evaluation_selection
            payload["status"] = "ready_for_host_workflow"
            payload["workflowArgs"] = workflow_args
            if not args.dry_run:
                try:
                    payload["portableTask"] = portable_task(
                        project_dir,
                        workflow_args,
                        run_id,
                        (args.runs_dir or project_dir / "runs").resolve(),
                    )
                except ValueError as exc:
                    payload["status"] = "run_setup_failed"
                    payload["error"] = str(exc)
                    return emit(payload, 2)
    return emit(payload, 0 if not copied["error"] else 2)


def command_finalize(args: argparse.Namespace) -> int:
    try:
        task_path = args.task.resolve()
        result_path = args.result.resolve()
        task = read_json(task_path)
        if not isinstance(task, dict) or task.get("protocol") != TASK_PROTOCOL:
            raise ValueError("task_protocol_invalid")
        if result_path != Path(str(task.get("resultPath", ""))).resolve():
            raise ValueError("result_path_mismatch")
        result = read_json(result_path)
        if not isinstance(result, dict):
            raise ValueError("result_not_object")
        verified = validate_completed_result(task, result)
        receipt_path = task_path.parent / "receipt.json"
        receipt = {
            "protocol": TASK_PROTOCOL,
            "runId": task["runId"],
            "query": task["workflowArgs"]["query"],
            "resultPath": str(result_path),
            **verified,
        }
        archive_blocked_receipt_for_completion(receipt_path, verified)
        write_once(receipt_path, receipt)
        return emit({"ok": True, "receiptPath": str(receipt_path), **receipt})
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return emit({"ok": False, "error": str(exc)}, 2)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Portable preflight for Meituan search evaluation.")
    commands = root.add_subparsers(dest="command", required=True)

    discover = commands.add_parser("discover", help="Discover canonical project screenshots.")
    discover.add_argument("--screenshot-dir", required=True, type=Path)
    discover.add_argument("--min-bytes", type=int, default=5001)
    discover.set_defaults(handler=command_discover)

    copy = commands.add_parser("copy", aliases=["intake"], help="Copy external screenshots into the project without renaming them.")
    copy.add_argument("--source-dir", required=True, type=Path, help="External screenshot directory or a single screenshot file.")
    copy.add_argument("--screenshot-dir", required=True, type=Path)
    copy.add_argument("--dry-run", action="store_true")
    copy.set_defaults(handler=command_copy)

    prepare = commands.add_parser("prepare-evaluate", help="Copy, discover, and emit host Workflow arguments.")
    prepare.add_argument("--project-dir", default=PROJECT_DIR, type=Path)
    prepare.add_argument("--source-dir", required=True, type=Path, help="External screenshot directory or a single screenshot file.")
    prepare.add_argument("--screenshot-dir", type=Path)
    prepare.add_argument("--query", default="")
    prepare.add_argument("--dimensions", nargs="+", default=["phase3-card_or_component-eval"])
    prepare.add_argument(
        "--evaluation-selection",
        default="",
        help='JSON：{"mode":"full_19"}、{"mode":"dimensions","dimensions":[...]} 或 {"mode":"custom_skills","skills":[{"dimension":"...","skill":"..."}]}。未传时兼容 --dimensions。',
    )
    prepare.add_argument("--report-outlet", choices=["local_html", "nocode"], default="local_html")
    prepare.add_argument("--min-bytes", type=int, default=5001)
    prepare.add_argument("--dry-run", action="store_true")
    prepare.add_argument("--run-id", default="", help="Unique portable run id; defaults to a generated id.")
    prepare.add_argument("--runs-dir", type=Path, help="Defaults to <project-dir>/runs.")
    prepare.set_defaults(handler=command_prepare)

    finalize = commands.add_parser("finalize-evaluate", help="Verify a host result and write an immutable delivery receipt.")
    finalize.add_argument("--task", required=True, type=Path)
    finalize.add_argument("--result", required=True, type=Path)
    finalize.set_defaults(handler=command_finalize)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
