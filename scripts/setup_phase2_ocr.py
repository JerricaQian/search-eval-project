#!/usr/bin/env python3
"""Install, provision, and verify the local Phase2 PaddleOCR backend.

Run this with the exact Python interpreter that will execute Phase2. Model
archives come from Paddle's official BOS model host and are SHA-256 verified
before extraction into the gitignored project-local runtime directory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = ROOT / "phase2-card-annotation" / "models" / "paddleocr"
CACHE_ROOT = ROOT / ".artifacts" / "paddlex-cache"
PADDLE_CPU_INDEX = "https://www.paddlepaddle.org.cn/packages/stable/cpu/"
PADDLE_VERSION = "3.3.1"
PADDLEOCR_VERSION = "3.7.0"
MODEL_SPECS = (
    {
        "name": "PP-OCRv5_server_det",
        "directory": "PP-OCRv5_server_det_infer",
        "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_server_det_infer.tar",
        "sha256": "22a33e0ba6a21425ea4192da03bf4395c9a0c67902bd924b7328fc859073045d",
        "files": {
            "inference.yml": "28fb721efc3634fc8aa677e474b9602cb815a91cf569ef357a7a553d7b3ce685",
            "inference.json": "af5876933d8806a1b50d895867e0781e135cd92ff37381992828fc8d1b842d28",
            "inference.pdiparams": "183146fe9d9910352f68482f623bcbbb9fa7b9e8fa1463b9ad288cef00524d2d",
        },
    },
    {
        "name": "PP-OCRv5_server_rec",
        "directory": "PP-OCRv5_server_rec_infer",
        "url": "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_server_rec_infer.tar",
        "sha256": "d99be2ffd348943ab52876179168be4fb5b14f5f0812f2ae4c76d89ec2ea750a",
        "files": {
            "inference.yml": "2c719dba044c4e2228aef8ff92f5f575394d75d24c16de096a33b7cfd902f66d",
            "inference.json": "8e6e12e5d42531840310977fffb58165bf889fc5061408c5a8afdb6985f47fcb",
            "inference.pdiparams": "63853f062a5f4089befc16f565a68277618e0da5cb45468b49d11079de0ada77",
        },
    },
)
REQUIRED_MODEL_FILES = ("inference.yml", "inference.json", "inference.pdiparams")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_ready(spec: dict[str, Any]) -> bool:
    directory = MODEL_ROOT / spec["directory"]
    files = spec["files"]
    return all((directory / name).is_file() and sha256(directory / name) == files[name] for name in REQUIRED_MODEL_FILES)


def install_packages() -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", f"paddlepaddle=={PADDLE_VERSION}", "-i", PADDLE_CPU_INDEX],
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements-ocr.txt")],
        check=True,
    )


def safe_extract(archive: Path, destination: Path, expected_directory: str) -> None:
    with tarfile.open(archive) as package:
        members = package.getmembers()
        prefix = expected_directory + "/"
        for member in members:
            if member.issym() or member.islnk():
                raise RuntimeError(f"unsafe_model_archive_link:{member.name}")
            if member.name == expected_directory:
                continue
            if not member.name.startswith(prefix) or ".." in Path(member.name).parts:
                raise RuntimeError(f"unsafe_model_archive_member:{member.name}")
        package.extractall(destination, members=members)


def provision_model(spec: dict[str, Any]) -> str:
    if model_ready(spec):
        return "already_ready"
    destination = MODEL_ROOT / spec["directory"]
    if destination.exists():
        raise RuntimeError(f"incomplete_model_directory:{destination}; remove it and rerun")
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase2-paddle-model-", dir=MODEL_ROOT) as temp_name:
        temp = Path(temp_name)
        archive = temp / f"{spec['directory']}.tar"
        urllib.request.urlretrieve(spec["url"], archive)
        actual = sha256(archive)
        if actual != spec["sha256"]:
            raise RuntimeError(f"model_sha256_mismatch:{spec['name']}:{actual}")
        extract_root = temp / "extract"
        extract_root.mkdir()
        safe_extract(archive, extract_root, spec["directory"])
        extracted = extract_root / spec["directory"]
        if not all((extracted / name).is_file() for name in REQUIRED_MODEL_FILES):
            raise RuntimeError(f"model_package_incomplete:{spec['name']}")
        shutil.move(str(extracted), str(destination))
    return "downloaded_and_verified"


def configure_cache() -> None:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(CACHE_ROOT))
    os.environ.setdefault("MPLCONFIGDIR", str(CACHE_ROOT / "matplotlib"))
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")


def health() -> dict[str, Any]:
    configure_cache()
    expected_versions = {"paddle": PADDLE_VERSION, "paddleocr": PADDLEOCR_VERSION}
    distributions = {"paddle": "paddlepaddle", "paddleocr": "paddleocr"}
    versions: dict[str, str] = {}
    packages = {
        "paddle": importlib.util.find_spec("paddle") is not None,
        "paddleocr": importlib.util.find_spec("paddleocr") is not None,
    }
    for module_name, distribution in distributions.items():
        if packages[module_name]:
            try:
                versions[module_name] = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                packages[module_name] = False
    for module_name, expected in expected_versions.items():
        if versions.get(module_name) != expected:
            packages[module_name] = False
    models = {spec["name"]: model_ready(spec) for spec in MODEL_SPECS}
    runtime_error = ""
    if packages["paddle"]:
        try:
            import paddle  # type: ignore[import-not-found]

            _ = paddle.__version__
        except Exception as exc:
            packages["paddle"] = False
            runtime_error = f"{type(exc).__name__}:{exc}"[:300]
    return {
        "python": sys.executable,
        "pythonVersion": sys.version.split()[0],
        "packages": packages,
        "packageVersions": versions,
        "expectedPackageVersions": expected_versions,
        "models": models,
        "runtimeError": runtime_error,
        "ready": all(packages.values()) and all(models.values()),
    }


def smoke_test() -> dict[str, Any]:
    status = health()
    if not status["ready"]:
        return {"passed": False, "error": "health_check_not_ready", "health": status}
    try:
        from PIL import Image, ImageDraw
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]

        detector = MODEL_ROOT / "PP-OCRv5_server_det_infer"
        recognizer = MODEL_ROOT / "PP-OCRv5_server_rec_infer"
        engine = PaddleOCR(
            text_detection_model_name="PP-OCRv5_server_det",
            text_detection_model_dir=str(detector),
            text_recognition_model_name="PP-OCRv5_server_rec",
            text_recognition_model_dir=str(recognizer),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            image = Image.new("RGB", (420, 100), "white")
            ImageDraw.Draw(image).text((20, 30), "Phase2 OCR 123", fill="black")
            image.save(handle.name)
            raw = list(engine.predict(handle.name)) if hasattr(engine, "predict") else engine.ocr(handle.name, cls=False)
        return {"passed": isinstance(raw, list), "results": len(raw) if isinstance(raw, list) else 0, "error": ""}
    except Exception as exc:
        return {"passed": False, "error": f"{type(exc).__name__}:{exc}"[:500]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the reproducible Phase2 PaddleOCR runtime")
    parser.add_argument("--install", action="store_true", help="Install PaddlePaddle and PaddleOCR into this Python")
    parser.add_argument("--download-models", action="store_true", help="Download and SHA-256 verify the two pinned models")
    parser.add_argument("--check", action="store_true", help="Check packages and model files")
    parser.add_argument("--smoke-test", action="store_true", help="Initialize PaddleOCR and run one local inference")
    parser.add_argument("--all", action="store_true", help="Install packages, provision models, check, and smoke test")
    args = parser.parse_args()
    if not any((args.install, args.download_models, args.check, args.smoke_test, args.all)):
        parser.error("choose --all or one or more actions")
    result: dict[str, Any] = {"contractVersion": "phase2.paddleocr-setup.v1"}
    try:
        if args.install or args.all:
            install_packages()
            result["installation"] = "complete"
        if args.download_models or args.all:
            result["modelProvisioning"] = {spec["name"]: provision_model(spec) for spec in MODEL_SPECS}
        if args.check or args.smoke_test or args.all:
            result["health"] = health()
        if args.smoke_test or args.all:
            result["smokeTest"] = smoke_test()
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"[:600]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "health" in result and not result["health"]["ready"]:
        return 1
    if "smokeTest" in result and not result["smokeTest"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
