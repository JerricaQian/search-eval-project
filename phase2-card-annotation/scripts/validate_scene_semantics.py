#!/usr/bin/env python3
"""阻断本地标注任务中可由页面上下文确定的结构性错误。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FORBIDDEN_ON_CONTINUATION = re.compile(r"(?:^|_)(?:Tab|图筛|营销横幅)(?:_|$)")
FORBIDDEN_CONTINUATION_ROLES = {"channel_tab", "graphical_filter", "promotional_banner"}
CARD_BORDER = re.compile(r"(?:商家卡|商卡|商品卡).+_border$")
HEAD_IMAGE_LABEL = re.compile(r"头图区$")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 SceneSpec 的续屏、截断卡与异构组件语义约束")
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()

    try:
        spec: dict[str, Any] = json.loads(args.spec.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"valid": False, "errors": [f"json_parse:{exc}"]}, ensure_ascii=False))
        return 2

    context = spec.get("page_context")
    annotations = spec.get("annotations")
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(context, dict):
        fail(errors, "page_context_required")
        context = {}
    if not isinstance(annotations, list) or not annotations:
        fail(errors, "annotations_required")
        annotations = []

    screen = context.get("screen")
    if not isinstance(screen, int) or screen < 1:
        fail(errors, "page_context.screen_must_be_positive_integer")
    continuation = context.get("is_continuation")
    if not isinstance(continuation, bool):
        fail(errors, "page_context.is_continuation_must_be_boolean")

    labels = [str(task.get("label", "")) for task in annotations if isinstance(task, dict)]
    border_tasks = [task for task in annotations if isinstance(task, dict) and task.get("kind") == "border" and CARD_BORDER.search(str(task.get("label", "")))]

    if screen and screen > 1:
        if continuation is not True:
            fail(errors, "screen_gt_1_must_explicitly_declare_is_continuation_true_or_split_into_new_page_type")
        forbidden = [label for label in labels if FORBIDDEN_ON_CONTINUATION.search(label)]
        forbidden_roles = [
            str(task.get("id", task.get("label", "")))
            for task in annotations
            if isinstance(task, dict) and task.get("semantic_role") in FORBIDDEN_CONTINUATION_ROLES
        ]
        if forbidden or forbidden_roles:
            details = forbidden + forbidden_roles
            fail(errors, f"continuation_forbids_inherited_top_components:{','.join(details)}")
        if not border_tasks:
            fail(errors, "continuation_requires_visible_first_card_border")
        else:
            first = min(border_tasks, key=lambda task: int(task.get("y", 10**9)))
            # 续屏顶部也可能先出现真实的状态栏、导航、快筛或异构模块。
            # 仅当首个可见商卡紧贴画布顶部时，才强制要求它声明为截断卡；
            # 不要求任何商卡必须从 y=0 开始。
            if int(first.get("y", 10**9)) <= 2 and not first.get("cropped"):
                fail(errors, f"continuation_top_card_must_set_cropped_true:{first.get('id', first.get('label'))}")

    below_tab = context.get("below_tab_component")
    if screen == 1:
        if below_tab not in {"运营聚合卡", "图筛", "无"}:
            fail(errors, "screen_1_requires_below_tab_component_assertion")
        if below_tab == "运营聚合卡":
            hetero = [task for task in annotations if isinstance(task, dict) and task.get("kind") == "hetero" and "运营聚合卡" in str(task.get("label", ""))]
            if not hetero:
                fail(errors, "below_tab_declared_heterogeneous_but_no_hetero_annotation")
            if any("图筛" in label for label in labels):
                fail(errors, "below_tab_declared_heterogeneous_but_graphical_filter_exists")

    # 对可见起点不在画布顶部、且不是“续页可见尾部”的标准商卡，要求显式标注真实头图区。
    # 这样能阻断把整张左图右文卡仅拆成“商家信息/标签/下挂”的模板化遗漏。
    for card in border_tasks:
        label = str(card.get("label", ""))
        if "续页可见尾部" in label or int(card.get("y", 0)) <= 2:
            continue
        card_id = str(card.get("id", ""))
        has_head_image = any(
            isinstance(task, dict)
            and task.get("parent") == card_id
            and HEAD_IMAGE_LABEL.search(str(task.get("label", "")))
            for task in annotations
        )
        if not has_head_image:
            fail(errors, f"standard_card_requires_visible_header_image:{card_id or label}")

    result = {"valid": not errors, "errors": errors, "warnings": warnings}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
