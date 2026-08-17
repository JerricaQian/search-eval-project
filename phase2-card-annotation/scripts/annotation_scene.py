#!/usr/bin/env python3
"""Phase2 SceneSpec 的唯一本地标注执行器。

场景事实保存在 JSON SceneSpec；本程序只校验、渲染和输出审计。
新 SceneSpec 必须使用 ``project://screenshots/...`` 与
``project://screenshots-out/...``，从而避免逐词脚本的硬编码路径漂移。

用法：
    python3 scripts/annotation_scene.py scenes/example.scene.json
    python3 scripts/annotation_scene.py scenes/example.scene.json --dry-run

历史 SceneSpec 仅可审计复现：
    python3 scripts/annotation_scene.py scenes/legacy.json --allow-legacy
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

from annotate_image import annotate_image

CONTRACT_VERSION = "phase2.scene-spec.v1"
VALID_KINDS = {"macro", "border", "part", "hetero"}
REQUIRED_TOP_LEVEL_FIELDS = {
    "contractVersion", "scene_id", "input", "output", "canvas", "coordinate_space",
    "page_context", "annotations",
}
REQUIRED_TASK_FIELDS = {"id", "label", "x", "y", "w", "h", "kind", "source", "semantic_role"}


def _fail(message: str) -> None:
    raise ValueError(message)


def default_project_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_path(spec_path: Path, raw_path: str, project_dir: Path) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        _fail("input/output 必须为非空路径字符串")
    prefix = "project://"
    if raw_path.startswith(prefix):
        return (project_dir / raw_path.removeprefix(prefix)).resolve()
    path = Path(raw_path)
    return path.resolve() if path.is_absolute() else (spec_path.parent / path).resolve()


def load_spec(spec_path: Path, allow_legacy: bool) -> dict[str, Any]:
    with spec_path.open(encoding="utf-8") as file:
        spec = json.load(file)
    if not isinstance(spec, dict):
        _fail("SceneSpec 顶层必须为对象")
    if allow_legacy:
        for field in ("scene_id", "input", "output", "annotations"):
            if field not in spec:
                _fail(f"SceneSpec 缺少顶层字段: {field}")
    else:
        missing = REQUIRED_TOP_LEVEL_FIELDS - spec.keys()
        if missing:
            _fail(f"SceneSpec 缺少统一契约字段: {sorted(missing)}")
        if spec.get("contractVersion") != CONTRACT_VERSION:
            _fail(f"contractVersion 必须为 {CONTRACT_VERSION}")
        if spec.get("coordinate_space") != "image_pixel":
            _fail("coordinate_space 必须为 image_pixel")
        if not str(spec["input"]).startswith("project://screenshots/"):
            _fail("input 必须使用 project://screenshots/ 项目级路径")
        if not str(spec["output"]).startswith("project://screenshots-out/"):
            _fail("output 必须使用 project://screenshots-out/ 项目级路径")
    if not isinstance(spec["annotations"], list) or not spec["annotations"]:
        _fail("annotations 必须是非空数组")
    return spec


def task_box(task: dict[str, Any]) -> tuple[int, int, int, int]:
    return (task["x"], task["y"], task["x"] + task["w"], task["y"] + task["h"])


def validate_spec(spec: dict[str, Any], image_size: tuple[int, int], allow_legacy: bool) -> list[str]:
    """返回非阻断告警；结构、几何或统一契约错误直接抛异常。"""
    width, height = image_size
    task_ids: list[str] = []
    warnings: list[str] = []
    cards: dict[str, dict[str, Any]] = {}

    for index, task in enumerate(spec["annotations"], start=1):
        if not isinstance(task, dict):
            _fail(f"第 {index} 个 annotation 不是对象")
        required_fields = REQUIRED_TASK_FIELDS if not allow_legacy else {"id", "label", "x", "y", "w", "h", "kind"}
        missing = required_fields - task.keys()
        if missing:
            _fail(f"第 {index} 个 annotation 缺少字段: {sorted(missing)}")
        if not isinstance(task["id"], str) or not task["id"].strip():
            _fail(f"第 {index} 个 annotation 的 id 必须为非空字符串")
        task_ids.append(task["id"])
        if task["kind"] not in VALID_KINDS:
            _fail(f"{task['id']}: kind 必须为 {sorted(VALID_KINDS)}")
        for key in ("x", "y", "w", "h"):
            if not isinstance(task[key], int):
                _fail(f"{task['id']}: {key} 必须为整数像素")
        if task["w"] <= 0 or task["h"] <= 0:
            _fail(f"{task['id']}: w/h 必须大于 0")
        x0, y0, x1, y1 = task_box(task)
        if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
            _fail(f"{task['id']}: 框 {x0},{y0},{x1},{y1} 超出画布 {width}x{height}")
        if task["kind"] == "border":
            cards[task["id"]] = task
        if task["kind"] == "part" and not task.get("parent"):
            if allow_legacy:
                warnings.append(f"{task['id']}: 历史 part 未声明 parent，无法做卡级审计")
            else:
                _fail(f"{task['id']}: part 必须声明 parent")

    duplicate_ids = [item for item, count in Counter(task_ids).items() if count > 1]
    if duplicate_ids:
        _fail(f"annotation id 重复: {duplicate_ids}")

    declared_canvas = spec.get("canvas")
    if not isinstance(declared_canvas, dict) or (declared_canvas.get("width"), declared_canvas.get("height")) != image_size:
        _fail(f"声明画布 {declared_canvas} 与输入图片实际尺寸 {width}x{height} 不一致")

    for task in spec["annotations"]:
        parent = task.get("parent")
        if not parent:
            continue
        if parent not in cards:
            _fail(f"{task['id']}: parent={parent} 必须指向 border 任务")
        px0, py0, px1, py1 = task_box(cards[parent])
        x0, y0, x1, y1 = task_box(task)
        if not (px0 <= x0 <= x1 <= px1 and py0 <= y0 <= y1 <= py1):
            warnings.append(f"{task['id']}: 未完全包含于 parent={parent}；请确认是否为合法跨卡内容")
    return warnings


def render_tasks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {key: task[key] for key in ("label", "x", "y", "w", "h", "kind", "elementId") if key in task}
        for task in spec["annotations"]
    ]


def build_report(spec: dict[str, Any], image_size: tuple[int, int], warnings: list[str], output_path: Path, project_dir: Path) -> dict[str, Any]:
    annotations = spec["annotations"]
    return {
        "contractVersion": spec.get("contractVersion", "legacy"),
        "scene_id": spec["scene_id"],
        "input": spec["input"],
        "output": str(output_path),
        "projectDir": str(project_dir),
        "canvas": {"width": image_size[0], "height": image_size[1]},
        "task_count": len(annotations),
        "kind_counts": dict(Counter(task["kind"] for task in annotations)),
        "cropped_task_count": sum(bool(task.get("cropped")) for task in annotations),
        "heterogeneous_task_count": sum(task["kind"] == "hetero" for task in annotations),
        "warnings": warnings,
        "annotations": annotations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="按统一 SceneSpec 校验、渲染并审计本地截图标注")
    parser.add_argument("spec", type=Path, help="SceneSpec JSON 文件")
    parser.add_argument("--project-dir", type=Path, default=default_project_dir(), help="项目根目录；默认由执行器位置推导")
    parser.add_argument("--dry-run", action="store_true", help="只校验并生成报告，不生成 PNG")
    parser.add_argument("--report", type=Path, help="覆盖默认审计报告路径")
    parser.add_argument("--allow-legacy", action="store_true", help="仅用于历史 SceneSpec 审计复现；新任务禁止使用")
    parser.add_argument("--skip-semantic-validation", action="store_true", help="仅用于历史 SceneSpec 迁移；新场景禁止使用")
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    spec_path = args.spec.resolve()
    spec = load_spec(spec_path, args.allow_legacy)
    input_path = resolve_path(spec_path, spec["input"], project_dir)
    output_path = resolve_path(spec_path, spec["output"], project_dir)
    if not args.allow_legacy:
        if not is_relative_to(input_path, project_dir / "screenshots"):
            _fail(f"input 必须位于项目 screenshots/: {input_path}")
        if not is_relative_to(output_path, project_dir / "screenshots-out"):
            _fail(f"output 必须位于项目 screenshots-out/: {output_path}")
    if not input_path.is_file():
        _fail(f"输入图片不存在: {input_path}")

    with Image.open(input_path) as image:
        image_size = image.size
    warnings = validate_spec(spec, image_size, args.allow_legacy)
    if not args.skip_semantic_validation:
        semantic_validator = Path(__file__).with_name("validate_scene_semantics.py")
        semantic = subprocess.run([sys.executable, str(semantic_validator), str(spec_path)], check=False, capture_output=True, text=True)
        if semantic.returncode != 0:
            _fail(f"语义结构校验失败: {semantic.stdout.strip() or semantic.stderr.strip()}")

    report_path = args.report.resolve() if args.report else output_path.with_suffix(".report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotate_image(str(input_path), str(output_path), render_tasks(spec))

    report = build_report(spec, image_size, warnings, output_path, project_dir)
    report["rendered"] = not args.dry_run
    report["legacyMode"] = args.allow_legacy
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "report": str(report_path), "warnings": warnings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
