from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
INTAKE_PATH = PROJECT_DIR / "scripts" / "ingest_external_screenshots.py"
DISCOVERY_PATH = PROJECT_DIR / "scripts" / "discover_screenshot_groups.py"
CLI_PATH = PROJECT_DIR / "workflow" / "eval_cli.py"


def load_intake_module():
    spec = importlib.util.spec_from_file_location("external_screenshot_intake_test", INTAKE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_discovery_module():
    spec = importlib.util.spec_from_file_location("screenshot_discovery_test", DISCOVERY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExternalScreenshotCopyTest(unittest.TestCase):
    def test_copy_preserves_original_filename_and_source(self) -> None:
        module = load_intake_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "external"
            destination_dir = root / "project" / "screenshots"
            source_dir.mkdir(parents=True)
            source = source_dir / "布洛芬_全部_1_副本.png"
            Image.new("RGB", (100, 100), "white").save(source)
            source_hash = digest(source)

            result = module.ingest(source_dir, destination_dir)

            destination = destination_dir / "布洛芬_全部_1_副本.png"
            self.assertEqual(result["error"], "")
            self.assertTrue(destination.exists())
            self.assertEqual(digest(source), source_hash, "copy must not modify the source file")
            self.assertEqual(digest(destination), source_hash)
            self.assertEqual(len(result["copied"]), 1)
            self.assertEqual(result["copied"][0]["destinationPath"], str(destination.resolve()))
            self.assertEqual(result["copied"][0]["sourcePath"], str(source.resolve()))

    def test_conflicting_destination_is_renamed_without_overwrite(self) -> None:
        module = load_intake_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "external"
            destination_dir = root / "project" / "screenshots"
            source_dir.mkdir(parents=True)
            destination_dir.mkdir(parents=True)
            source = source_dir / "库迪_全部_1_副本.png"
            destination = destination_dir / "库迪_全部_1_副本.png"
            Image.new("RGB", (100, 100), "white").save(source)
            Image.new("RGB", (100, 100), "black").save(destination)
            destination_hash = digest(destination)

            result = module.ingest(source_dir, destination_dir)

            self.assertEqual(result["error"], "")
            self.assertEqual(result["renamed"][0]["destinationPath"], str((destination_dir / "库迪_全部_1_副本2.png").resolve()))
            self.assertTrue((destination_dir / "库迪_全部_1_副本2.png").exists())
            self.assertEqual(digest(destination), destination_hash)

    def test_renamed_copy_is_not_grouped_as_its_original_screenshot(self) -> None:
        discovery = load_discovery_module()
        with tempfile.TemporaryDirectory() as tmp:
            screenshot_dir = Path(tmp) / "screenshots"
            screenshot_dir.mkdir()
            original = screenshot_dir / "库迪_全部_1.png"
            renamed = screenshot_dir / "库迪_全部_1_副本2.png"
            Image.new("RGB", (100, 100), "white").save(original)
            Image.new("RGB", (100, 100), "black").save(renamed)

            result = discovery.discover(screenshot_dir, min_bytes=1)

            self.assertEqual(result["groups"][0]["files"], [str(original.resolve())])
            self.assertEqual(result["unparseableFiles"], [str(renamed.resolve())])

    def test_single_file_is_copied_with_its_original_filename(self) -> None:
        module = load_intake_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "外部" / "万达广场_全部_1_副本.png"
            destination_dir = root / "project" / "screenshots"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (100, 100), "white").save(source)

            result = module.ingest(source, destination_dir)

            self.assertEqual(result["error"], "")
            self.assertEqual(result["copied"][0]["sourcePath"], str(source.resolve()))
            self.assertTrue((destination_dir / "万达广场_全部_1_副本.png").exists())

    def test_prepare_cli_emits_host_workflow_handoff_after_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "external"
            project_dir = root / "project"
            source_dir.mkdir(parents=True)
            Image.new("RGB", (100, 100), "white").save(source_dir / "露营_全部_1.png")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "prepare-evaluate",
                    "--project-dir",
                    str(project_dir),
                    "--source-dir",
                    str(source_dir),
                    "--query",
                    "露营",
                    "--min-bytes",
                    "1",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertEqual(payload["protocol"], "MEITUAN_EVAL_HANDOFF_V1")
            self.assertEqual(payload["status"], "ready_for_host_workflow")
            self.assertEqual(payload["workflowArgs"]["mode"], "evaluate_only")
            self.assertEqual(payload["workflowArgs"]["selectedScreenshots"], [
                str((project_dir / "screenshots" / "露营_全部_1.png").resolve())
            ])
