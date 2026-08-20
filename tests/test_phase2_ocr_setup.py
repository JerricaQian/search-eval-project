from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = PROJECT_DIR / "scripts/setup_phase2_ocr.py"


def load_setup_module():
    spec = importlib.util.spec_from_file_location("phase2_ocr_setup_test", SETUP_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Phase2OcrSetupTest(unittest.TestCase):
    def test_models_are_pinned_to_official_bos_archives(self) -> None:
        module = load_setup_module()
        self.assertEqual(module.PADDLE_VERSION, "3.3.1")
        self.assertEqual(module.PADDLEOCR_VERSION, "3.7.0")
        self.assertEqual({item["name"] for item in module.MODEL_SPECS}, {"PP-OCRv5_server_det", "PP-OCRv5_server_rec"})
        for item in module.MODEL_SPECS:
            self.assertTrue(item["url"].startswith("https://paddle-model-ecology.bj.bcebos.com/"))
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")

    def test_model_archive_rejects_path_traversal(self) -> None:
        module = load_setup_module()
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            archive = temp / "bad.tar"
            payload = b"bad"
            with tarfile.open(archive, "w") as package:
                member = tarfile.TarInfo("../escape")
                member.size = len(payload)
                package.addfile(member, io.BytesIO(payload))
            with self.assertRaisesRegex(RuntimeError, "unsafe_model_archive_member"):
                module.safe_extract(archive, temp / "extract", "expected")


if __name__ == "__main__":
    unittest.main()
