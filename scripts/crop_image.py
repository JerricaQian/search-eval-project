#!/usr/bin/env python3
"""Create one bounded image crop without relying on a host-specific image tool."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def non_negative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--x", required=True, type=non_negative_int)
    parser.add_argument("--y", required=True, type=non_negative_int)
    parser.add_argument("--width", required=True, type=positive_int)
    parser.add_argument("--height", required=True, type=positive_int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.input.resolve()
    output = args.output.resolve()
    if source == output:
        raise SystemExit("--output must differ from --input so the source screenshot is preserved")
    if not source.is_file():
        raise SystemExit(f"input image does not exist: {source}")

    with Image.open(source) as image:
        image.load()
        if args.x + args.width > image.width or args.y + args.height > image.height:
            raise SystemExit(
                f"crop [{args.x}, {args.y}, {args.width}, {args.height}] exceeds image "
                f"size [{image.width}, {image.height}]"
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        image.crop((args.x, args.y, args.x + args.width, args.y + args.height)).save(output)

    print(json.dumps({
        "input": str(source),
        "output": str(output),
        "bounds": [args.x, args.y, args.width, args.height],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
