#!/usr/bin/env python3
"""Resumable, single-query controller for Meituan Phase1 capture.

The controller never drives Android directly.  Each attempted query invokes the
existing ``run_scroll.sh`` once, then records an append-only receipt.  This
keeps a paused batch auditable and prevents an observer from accidentally
starting a competing device-control process.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fail(message: str) -> None:
    raise SystemExit(message)


def json_line(path: Path, event: dict[str, Any]) -> None:
    event = {"at": now(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def read_events(batch_dir: Path) -> list[dict[str, Any]]:
    events_path = batch_dir / "events.jsonl"
    if not events_path.is_file():
        fail(f"缺少批次事件文件: {events_path}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            fail(f"事件文件第 {line_number} 行不是有效 JSON: {exc}")
    if not events or events[0].get("event") != "initialized":
        fail(f"批次缺少 initialized 事件: {events_path}")
    return events


def config_from(events: list[dict[str, Any]]) -> dict[str, Any]:
    return events[0]["config"]


def state_from(events: list[dict[str, Any]]) -> dict[str, Any]:
    config = config_from(events)
    queries = config["queries"]
    query_state: dict[str, dict[str, Any]] = {
        query: {"status": "pending", "attempts": 0, "receipts": []} for query in queries
    }
    paused = False
    blocked = False
    for event in events[1:]:
        kind = event.get("event")
        query = event.get("query")
        if kind == "pause_requested":
            paused = True
        elif kind == "resumed":
            paused = False
            blocked = False
        elif kind == "batch_blocked":
            blocked = True
        elif kind == "attempt_started" and query in query_state:
            query_state[query]["status"] = "running"
            query_state[query]["attempts"] += 1
        elif kind == "attempt_interrupted" and query in query_state:
            # A controller may be terminated while its child script is active.
            # There is no completion receipt in that case, so make the word
            # eligible again and preserve the interruption as an event.
            query_state[query]["status"] = "pending"
        elif kind == "attempt_finished" and query in query_state:
            query_state[query]["status"] = event["status"]
            query_state[query]["receipts"].append(event)
    counts: dict[str, int] = {}
    for item in query_state.values():
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"paused": paused, "blocked": blocked, "queries": query_state, "counts": counts}


def batch_dir_for(project_dir: Path, batch_id: str) -> Path:
    if not batch_id or any(char in batch_id for char in "/\\\r\n"):
        fail("batch-id 不能为空，且不得含路径分隔符或换行")
    return project_dir / ".artifacts" / "过程文件-评测结果与审计" / "capture" / batch_id


def parse_queries(raw: str | None, query_file: Path | None) -> list[str]:
    if bool(raw) == bool(query_file):
        fail("必须二选一提供 --queries 或 --queries-file")
    source = raw if raw is not None else query_file.read_text(encoding="utf-8")
    queries = [item.strip() for item in source.replace("\n", ",").split(",") if item.strip()]
    if not queries:
        fail("搜索词不能为空")
    if len(set(queries)) != len(queries):
        fail("同一批次不允许重复搜索词；请保留不同的近似词但移除完全重复项")
    if any("_" in query for query in queries):
        fail("搜索词不得包含下划线，以保证截图文件名可解析")
    return queries


def parse_csv(value: str, allowed: set[str], field: str) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    if not values or any(item not in allowed for item in values):
        fail(f"{field} 只允许: {', '.join(sorted(allowed))}")
    return values


def acquire_lock(batch_dir: Path) -> Path:
    lock_dir = batch_dir / "active.lock"
    try:
        lock_dir.mkdir()
    except FileExistsError:
        owner = lock_dir / "owner.json"
        fail(f"批次已有活动控制器锁: {owner}；请先 pause/status，勿启动第二个设备任务")
    with (lock_dir / "owner.json").open("x", encoding="utf-8") as handle:
        json.dump({"pid": os.getpid(), "startedAt": now()}, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    return lock_dir


def release_lock(lock_dir: Path) -> None:
    released = lock_dir.with_name(f"lock.released.{int(time.time() * 1000)}.{os.getpid()}")
    lock_dir.rename(released)


def png_is_valid(path: Path) -> bool:
    try:
        return path.stat().st_size > 5000 and path.open("rb").read(8) == PNG_SIGNATURE
    except OSError:
        return False


def expected_names(query: str, tabs: list[str], screens: list[str]) -> list[str]:
    return [f"{query}_{tab}_{screen}" for tab in tabs for screen in screens]


def matching_pngs(screenshot_dir: Path, prefix: str) -> set[Path]:
    return {path.resolve() for path in screenshot_dir.glob(prefix + "*.png") if path.is_file()}


def preflight(config: dict[str, Any]) -> tuple[bool, str]:
    checks = [
        (["adb", "get-state"], "device"),
        (["adb", "shell", "ime", "list", "-s"], "com.android.adbkeyboard/.AdbIME"),
        (["adb", "shell", "pm", "list", "packages", "com.sankuai.meituan"], "package:com.sankuai.meituan"),
    ]
    for command, required in checks:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        output = (completed.stdout + completed.stderr).replace("\r", "")
        if completed.returncode != 0 or required not in output:
            return False, f"预检失败: {' '.join(command)} -> {output.strip() or '无输出'}"
    return True, ""


def run_query(batch_dir: Path, config: dict[str, Any], query: str, attempt: int) -> dict[str, Any]:
    screenshot_dir = Path(config["screenshotDir"])
    runner = Path(config["runner"])
    tabs = config["tabs"]
    screens = config["screens"]
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{query}_"
    before = matching_pngs(screenshot_dir, prefix)
    attempt_dir = batch_dir / "attempts" / query
    attempt_dir.mkdir(parents=True, exist_ok=True)
    log_path = attempt_dir / f"attempt-{attempt:03d}.{int(time.time() * 1000)}.log"
    command = ["bash", str(runner), query, ",".join(tabs), ",".join(screens)]
    env = os.environ.copy()
    env["OUT"] = str(screenshot_dir)
    with log_path.open("x", encoding="utf-8") as handle:
        completed = subprocess.run(command, cwd=config["projectDir"], env=env, stdout=handle, stderr=subprocess.STDOUT, check=False)
    after = matching_pngs(screenshot_dir, prefix)
    created = sorted(after - before)
    valid = [path for path in created if png_is_valid(path)]
    needed = expected_names(query, tabs, screens)
    present_prefixes = {path.name.split("_副本", 1)[0].removesuffix(".png") for path in valid}
    missing = [name for name in needed if name not in present_prefixes]
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    navigation_failed = any(marker in log_text for marker in (
        "无法回到搜索输入页",
        "当前不在搜索页或结果页",
        "搜索提交后未验证到结果页 Tab",
        "系统通知面板处于前台",
    ))
    return {
        "event": "attempt_finished",
        "query": query,
        "attempt": attempt,
        "status": "completed" if not missing else "failed",
        "exitCode": completed.returncode,
        "logPath": str(log_path),
        "newScreenshotPaths": [str(path) for path in created],
        "validScreenshotPaths": [str(path) for path in valid],
        "missing": missing,
        "inputVerificationFailed": "输入失败" in log_text,
        "navigationFailed": navigation_failed,
    }


def command_init(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    queries = parse_queries(args.queries, Path(args.queries_file) if args.queries_file else None)
    tabs = parse_csv(args.tabs, {"全部", "外卖", "团购"}, "tabs")
    screens = parse_csv(args.screens, {"1", "2", "3"}, "screens")
    batch_dir = batch_dir_for(project_dir, args.batch_id)
    batch_dir.mkdir(parents=True, exist_ok=True)
    events_path = batch_dir / "events.jsonl"
    config = {
        "batchId": args.batch_id,
        "projectDir": str(project_dir),
        "screenshotDir": str(Path(args.screenshot_dir or project_dir / "screenshots").resolve()),
        "runner": str((project_dir / "phase1-screenshot" / "scripts" / "run_scroll.sh").resolve()),
        "queries": queries,
        "tabs": tabs,
        "screens": screens,
    }
    if events_path.exists():
        existing = config_from(read_events(batch_dir))
        if existing != config:
            fail(f"批次已存在但配置不一致: {batch_dir}")
    else:
        json_line(events_path, {"event": "initialized", "config": config})
    print(json.dumps({"ok": True, "batchDir": str(batch_dir), "eventsPath": str(events_path)}, ensure_ascii=False))
    return 0


def command_status(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch_dir).resolve()
    events = read_events(batch_dir)
    print(json.dumps({"ok": True, "batchDir": str(batch_dir), "config": config_from(events), "state": state_from(events)}, ensure_ascii=False, indent=2))
    return 0


def command_pause(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch_dir).resolve()
    events_path = batch_dir / "events.jsonl"
    read_events(batch_dir)
    json_line(events_path, {"event": "pause_requested", "reason": args.reason})
    print(json.dumps({"ok": True, "batchDir": str(batch_dir), "status": "pause_requested"}, ensure_ascii=False))
    return 0


def command_run(args: argparse.Namespace) -> int:
    batch_dir = Path(args.batch_dir).resolve()
    events_path = batch_dir / "events.jsonl"
    events = read_events(batch_dir)
    config = config_from(events)
    if not Path(config["runner"]).is_file():
        fail(f"找不到截图脚本: {config['runner']}")
    lock_dir = acquire_lock(batch_dir)
    try:
        events = read_events(batch_dir)
        state = state_from(events)
        for query, item in state["queries"].items():
            if item["status"] == "running":
                json_line(events_path, {
                    "event": "attempt_interrupted",
                    "query": query,
                    "attempt": item["attempts"],
                    "reason": "controller_restarted_without_completion_receipt",
                })
        state = state_from(read_events(batch_dir))
        if (state["paused"] or state["blocked"]) and not args.resume:
            fail("批次处于暂停或输入校验阻断状态；修复环境后使用 run --resume 显式恢复")
        json_line(events_path, {"event": "resumed"})
        ok, error = preflight(config)
        if not ok:
            json_line(events_path, {"event": "preflight_failed", "error": error})
            fail(error)
        json_line(events_path, {"event": "preflight_passed"})
        state = state_from(read_events(batch_dir))
        for query in config["queries"]:
            item = state["queries"][query]
            eligible = item["status"] == "pending" or (args.retry_failed and item["status"] == "failed")
            if not eligible:
                continue
            if state_from(read_events(batch_dir))["paused"]:
                print(json.dumps({"ok": True, "batchDir": str(batch_dir), "status": "paused"}, ensure_ascii=False))
                return 0
            attempt = item["attempts"] + 1
            json_line(events_path, {"event": "attempt_started", "query": query, "attempt": attempt})
            receipt = run_query(batch_dir, config, query, attempt)
            json_line(events_path, receipt)
            # A query can legitimately have no result page.  Its receipt stays
            # failed, but the next query is allowed to return to SearchActivity
            # and continue.  Only failed text input blocks the entire batch.
            if receipt["inputVerificationFailed"]:
                json_line(events_path, {
                    "event": "batch_blocked",
                    "reason": "input_verification_failed",
                    "query": query,
                    "logPath": receipt["logPath"],
                })
                print(json.dumps({"ok": False, "batchDir": str(batch_dir), "status": "blocked", "query": query}, ensure_ascii=False))
                return 1
            state = state_from(read_events(batch_dir))
        final_state = state_from(read_events(batch_dir))
        if not final_state["paused"] and final_state["counts"].get("pending", 0) == 0:
            json_line(events_path, {"event": "batch_terminal", "counts": final_state["counts"]})
        print(json.dumps({"ok": True, "batchDir": str(batch_dir), "state": state_from(read_events(batch_dir))}, ensure_ascii=False))
        return 0
    finally:
        release_lock(lock_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="美团 Phase1 可恢复单词级截图控制器")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init", help="创建或验证一个不可变的批次配置")
    init.add_argument("--project-dir", required=True)
    init.add_argument("--batch-id", required=True)
    init.add_argument("--queries")
    init.add_argument("--queries-file")
    init.add_argument("--tabs", required=True)
    init.add_argument("--screens", required=True)
    init.add_argument("--screenshot-dir")
    init.set_defaults(func=command_init)
    status = subparsers.add_parser("status", help="读取批次状态；不会操作设备")
    status.add_argument("--batch-dir", required=True)
    status.set_defaults(func=command_status)
    pause = subparsers.add_parser("pause", help="请求在当前词结束后暂停")
    pause.add_argument("--batch-dir", required=True)
    pause.add_argument("--reason", default="user_requested")
    pause.set_defaults(func=command_pause)
    run = subparsers.add_parser("run", help="逐词调用 run_scroll.sh；一次只控制一个设备任务")
    run.add_argument("--batch-dir", required=True)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--retry-failed", action="store_true")
    run.set_defaults(func=command_run)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # Keep controller errors visible and non-destructive.
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
