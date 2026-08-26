from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "phase1-screenshot" / "scripts" / "discover_screenshot_groups.py"


def load_module():
    spec = importlib.util.spec_from_file_location("discover_screenshot_groups_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiscoverScreenshotGroupsTest(unittest.TestCase):
    def test_groups_valid_images_and_keeps_invalid_files_out_of_selection(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (80, 80), "white").save(root / "库迪_全部_1.png")
            Image.new("RGB", (80, 80), "white").save(root / "库迪_外卖_2.png")
            Image.new("RGB", (80, 80), "white").save(root / "含_下划线_全部_3.png")
            (root / "库迪_全部_2.png").write_bytes(b"")
            Image.new("RGB", (80, 80), "white").save(root / "unparseable.png")

            result = module.discover(root, min_bytes=1)

        self.assertEqual([group["query"] for group in result["groups"]], ["含_下划线", "库迪"])
        kudi = next(group for group in result["groups"] if group["query"] == "库迪")
        self.assertEqual(kudi["count"], 2)
        self.assertEqual(kudi["tabs"][0]["tab"], "全部")
        self.assertEqual(kudi["tabs"][0]["screens"], ["1"])
        self.assertEqual(len(result["invalidFiles"]), 1)
        self.assertEqual(len(result["unparseableFiles"]), 1)

    def test_missing_directory_is_reported_without_error(self) -> None:
        module = load_module()
        result = module.discover(Path("/tmp/not-a-real-screenshot-directory"), min_bytes=1)
        self.assertEqual(result["groups"], [])
        self.assertEqual(result["error"], "directory_not_found")

    def test_copy_suffixes_are_distinct_instances_not_query_text(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for suffix in ("", "_副本", "_副本2", "_副本(3)", "_copy4"):
                Image.new("RGB", (80, 80), "white").save(root / f"漂流_全部_1{suffix}.png")
            result = module.discover(root, min_bytes=1)

        self.assertEqual([group["query"] for group in result["groups"]], ["漂流"] * 5)
        self.assertEqual(
            [group["instance"] for group in result["groups"]],
            ["original", "副本", "副本2", "副本3", "副本4"],
        )
        self.assertEqual(result["unparseableFiles"], [])
