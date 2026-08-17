#!/usr/bin/env python3
"""创建符合统一契约的空白 Phase2 SceneSpec。

此工具只创建任务骨架，不推断页面语义、坐标或卡片结构。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

CONTRACT_VERSION = "phase2.scene-spec.v1"


def slug(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-")
    return normalized or "scene"


def project_uri(project_dir: Path, target: Path) -> str:
    return "project://" + target.resolve().relative_to(project_dir.resolve()).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="为指定项目截图创建统一 SceneSpec 骨架")
    parser.add_argument("--query", required=True, help="唯一搜索词")
    parser.add_argument("--screenshot", required=True, type=Path, help="项目 screenshots/ 下的截图路径")
    parser.add_argument("--scene", type=Path, help="输出 SceneSpec；默认 phase2-card-annotation/scenes/<截图名>.scene.json")
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--screen", type=int, default=1)
    parser.add_argument("--continuation", action="store_true")
    parser.add_argument("--below-tab-component", choices=("运营聚合卡", "图筛", "无"), default="无")
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    screenshot = args.screenshot.resolve()
    screenshots_dir = project_dir / "screenshots"
    if not screenshot.is_file() or screenshots_dir not in (screenshot, *screenshot.parents):
        raise ValueError(f"截图必须是项目 screenshots/ 下的现有文件: {screenshot}")
    if args.screen > 1 and not args.continuation:
        raise ValueError("screen 大于 1 时必须显式传入 --continuation")

    scene_path = args.scene.resolve() if args.scene else project_dir / "phase2-card-annotation" / "scenes" / f"{screenshot.stem}.scene.json"
    scenes_dir = project_dir / "phase2-card-annotation" / "scenes"
    if scenes_dir not in (scene_path, *scene_path.parents):
        raise ValueError(f"SceneSpec 必须写入 scenes/: {scene_path}")
    if scene_path.exists():
        raise ValueError(f"SceneSpec 已存在，拒绝覆盖: {scene_path}")

    with Image.open(screenshot) as image:
        width, height = image.size
    output = project_dir / "screenshots-out" / "annotations" / f"{screenshot.stem}_annotated.png"
    spec = {
        "contractVersion": CONTRACT_VERSION,
        "scene_id": f"{slug(args.query)}-{slug(screenshot.stem)}",
        "input": project_uri(project_dir, screenshot),
        "output": project_uri(project_dir, output),
        "canvas": {"width": width, "height": height},
        "coordinate_space": "image_pixel",
        "page_context": {
            "screen": args.screen,
            "is_continuation": args.continuation,
            "below_tab_component": args.below_tab_component if args.screen == 1 else "无",
        },
        "annotations": [],
    }
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    scene_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scene": str(scene_path), "output": spec["output"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
