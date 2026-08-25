from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
CROP_SCRIPT = PROJECT_DIR / "scripts" / "crop_image.py"


class CropImageTest(unittest.TestCase):
    def test_crops_bounded_region_without_modifying_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "crops" / "detail.png"
            image = Image.new("RGB", (8, 6), "white")
            image.putpixel((2, 1), (255, 0, 0))
            image.save(source)

            completed = subprocess.run(
                [
                    sys.executable, str(CROP_SCRIPT),
                    "--input", str(source), "--output", str(output),
                    "--x", "2", "--y", "1", "--width", "4", "--height", "3",
                ],
                check=True, capture_output=True, text=True,
            )

            self.assertEqual(json.loads(completed.stdout)["bounds"], [2, 1, 4, 3])
            with Image.open(source) as unchanged:
                self.assertEqual(unchanged.size, (8, 6))
            with Image.open(output) as cropped:
                self.assertEqual(cropped.size, (4, 3))
                self.assertEqual(cropped.getpixel((0, 0)), (255, 0, 0))

    def test_rejects_crop_outside_source_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "detail.png"
            Image.new("RGB", (8, 6), "white").save(source)

            completed = subprocess.run(
                [
                    sys.executable, str(CROP_SCRIPT),
                    "--input", str(source), "--output", str(output),
                    "--x", "6", "--y", "1", "--width", "4", "--height", "3",
                ],
                check=False, capture_output=True, text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("exceeds image size", completed.stderr)
            self.assertFalse(output.exists())
