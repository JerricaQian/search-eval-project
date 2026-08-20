#!/usr/bin/env python3
"""Portable preflight adapter for the host-injected evaluation Workflow.

The JS Workflow deliberately depends on a host that provides LLM agents. This
CLI handles the deterministic part that every host can share: copying external
screenshots, discovery, and a structured Workflow handoff request.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]


def load_module(filename: str, module_name: str) -> Any:
    path = PROJECT_DIR / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot_load:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


DISCOVERY = load_module("discover_screenshot_groups.py", "search_eval_discovery")
COPY = load_module("ingest_external_screenshots.py", "search_eval_copy")


def emit(payload: dict[str, Any], exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


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
        "protocol": "MEITUAN_EVAL_HANDOFF_V1",
        "projectDir": str(args.project_dir.resolve()),
        "copy": copied,
        "discovery": discovery,
        "status": "copy_blocked" if copied["error"] else "awaiting_screenshot_selection",
    }
    if not copied["error"] and args.query:
        group = next((item for item in discovery["groups"] if item["query"] == args.query), None)
        if group is None:
            payload["status"] = "query_not_found_after_copy"
        else:
            payload["status"] = "ready_for_host_workflow"
            payload["workflowArgs"] = {
                "mode": "evaluate_only",
                "projectDir": str(args.project_dir.resolve()),
                "selectedScreenshots": group["files"],
                "dimensions": args.dimensions,
                "reportOutlet": args.report_outlet,
                "phase2Mode": "lightweight",
            }
    return emit(payload, 0 if not copied["error"] else 2)


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
    prepare.add_argument("--report-outlet", choices=["local_html", "nocode"], default="local_html")
    prepare.add_argument("--min-bytes", type=int, default=5001)
    prepare.add_argument("--dry-run", action="store_true")
    prepare.set_defaults(handler=command_prepare)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
