from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
CLI_PATH = PROJECT_DIR / "workflow" / "eval_cli.py"


class PortableTaskProtocolTest(unittest.TestCase):
    def prepare(self, root: Path, run_id: str = "portable-01") -> dict:
        source = root / "external"
        project = root / "project"
        source.mkdir()
        project.mkdir()
        (project / "phase3-evaluation").symlink_to(PROJECT_DIR / "phase3-evaluation", target_is_directory=True)
        Image.new("RGB", (100, 100), "white").save(source / "露营_全部_1.png")
        completed = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "prepare-evaluate",
                "--project-dir", str(project), "--source-dir", str(source),
                "--query", "露营", "--min-bytes", "1", "--run-id", run_id,
            ],
            check=True, capture_output=True, text=True,
        )
        return json.loads(completed.stdout)

    def test_prepare_creates_immutable_task_and_rejects_duplicate_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.prepare(root)
            portable = payload["portableTask"]
            task_path = Path(portable["taskPath"])
            task = json.loads(task_path.read_text())

            self.assertEqual(portable["protocol"], "MEITUAN_EVAL_TASK_V3")
            self.assertEqual(task["runId"], "portable-01")
            self.assertEqual(task["workflowArgs"]["tag"], "portable-01")
            self.assertEqual(task["workflowArgs"]["batchId"], "portable-01")
            self.assertEqual(task["workflowArgs"]["rerunId"], "portable-01")
            self.assertEqual(task["workflowArgs"]["pythonBin"], sys.executable)
            self.assertTrue(task["contractFiles"][0].endswith("phase234-query-pipeline.md"))
            self.assertTrue(task["contractFiles"][1].endswith("evaluation-result.v3.schema.json"))

            source = root / "external"
            project = root / "project"
            repeated = subprocess.run(
                [
                    sys.executable, str(CLI_PATH), "prepare-evaluate",
                    "--project-dir", str(project), "--source-dir", str(source),
                    "--query", "露营", "--min-bytes", "1", "--run-id", "portable-01",
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(repeated.returncode, 2)
            self.assertEqual(json.loads(repeated.stdout)["status"], "run_setup_failed")

    def test_prepare_preserves_explicit_evaluation_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "external"
            project = root / "project"
            source.mkdir()
            project.mkdir()
            (project / "phase3-evaluation").symlink_to(PROJECT_DIR / "phase3-evaluation", target_is_directory=True)
            Image.new("RGB", (100, 100), "white").save(source / "露营_全部_1.png")
            selection = {"mode": "custom_skills", "skills": [
                {"dimension": "phase3-card_or_component-eval", "skill": "eval-8-info-redundancy"},
            ]}
            completed = subprocess.run(
                [
                    sys.executable, str(CLI_PATH), "prepare-evaluate",
                    "--project-dir", str(project), "--source-dir", str(source), "--query", "露营",
                    "--min-bytes", "1", "--run-id", "portable-selection",
                    "--evaluation-selection", json.dumps(selection, ensure_ascii=False),
                ],
                check=True, capture_output=True, text=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["workflowArgs"]["evaluationSelection"], selection)
            task = json.loads(Path(payload["portableTask"]["taskPath"]).read_text())
            self.assertEqual([(target["dimension"], target["skill"]) for target in task["evalTargets"]], [
                ("phase3-card_or_component-eval", "eval-8-info-redundancy"),
            ])
            task_project = Path(payload["workflowArgs"]["projectDir"])
            self.assertIn(str(task_project / "phase3-evaluation/dimensions/card-component/skills/eval-8-info-redundancy/SKILL.md"), task["requiredReads"])
            self.assertNotIn(str(task_project / "phase3-evaluation/dimensions/card-component/skills/eval-7-info-authenticity/SKILL.md"), task["requiredReads"])

    def test_finalize_accepts_only_complete_verified_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.prepare(root)
            project = root / "project"
            task_path = Path(payload["portableTask"]["taskPath"])
            result_path = Path(payload["portableTask"]["resultPath"])

            manifest = project / "screenshots-out" / "elements.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}")
            manifest_audit = project / "screenshots-out" / "elements.audit.json"
            manifest_audit.write_text('{"valid": true}')
            eval_result = project / ".artifacts" / "eval-results.json"
            eval_result.parent.mkdir(parents=True)
            eval_result.write_text("[]")
            eval_audit = project / ".artifacts" / "eval-audit.json"
            eval_audit.write_text('{"valid": true}')
            result_path.write_text(json.dumps({
                "ok": True,
                "query": "露营",
                "stageA": {"elementListPaths": [str(manifest)], "elementAuditPaths": [str(manifest_audit)]},
                "stageB": {"evalResultFile": str(eval_result), "evalAuditFile": str(eval_audit)},
                "stageC": {"evidenceImages": []},
                "stageD": {},
                "blockedAt": "",
                "error": "",
            }, ensure_ascii=False))

            completed = subprocess.run(
                [sys.executable, str(CLI_PATH), "finalize-evaluate", "--task", str(task_path), "--result", str(result_path)],
                check=True, capture_output=True, text=True,
            )
            receipt = json.loads(completed.stdout)
            self.assertEqual(receipt["status"], "completed")
            self.assertTrue(Path(receipt["receiptPath"]).is_file())

    def test_finalize_rejects_success_without_all_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.prepare(Path(tmp))
            task_path = Path(payload["portableTask"]["taskPath"])
            result_path = Path(payload["portableTask"]["resultPath"])
            result_path.write_text(json.dumps({"ok": True, "query": "露营", "blockedAt": "", "error": ""}))

            completed = subprocess.run(
                [sys.executable, str(CLI_PATH), "finalize-evaluate", "--task", str(task_path), "--result", str(result_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("successful_result_missing_stage", json.loads(completed.stdout)["error"])

    def test_finalize_keeps_existing_v2_report_contract_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.prepare(root)
            project = root / "project"
            task_path = Path(payload["portableTask"]["taskPath"])
            result_path = Path(payload["portableTask"]["resultPath"])
            task = json.loads(task_path.read_text())
            task["protocol"] = "MEITUAN_EVAL_TASK_V2"
            task_path.write_text(json.dumps(task))

            manifest = project / "screenshots-out" / "elements.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}")
            manifest_audit = project / "screenshots-out" / "elements.audit.json"
            manifest_audit.write_text('{"valid": true}')
            eval_result = project / ".artifacts" / "eval-results.json"
            eval_result.parent.mkdir(parents=True)
            eval_result.write_text("[]")
            eval_audit = project / ".artifacts" / "eval-audit.json"
            eval_audit.write_text('{"valid": true}')
            report = project / "reports" / "report.html"
            report.parent.mkdir(parents=True)
            report.write_text("<html></html>")
            result_path.write_text(json.dumps({
                "ok": True,
                "query": "露营",
                "stageA": {"elementListPaths": [str(manifest)], "elementAuditPaths": [str(manifest_audit)]},
                "stageB": {"evalResultFile": str(eval_result), "evalAuditFile": str(eval_audit)},
                "stageC": {"evidenceImages": []},
                "stageD": {"reportPath": str(report)},
                "blockedAt": "",
                "error": "",
            }, ensure_ascii=False))

            completed = subprocess.run(
                [sys.executable, str(CLI_PATH), "finalize-evaluate", "--task", str(task_path), "--result", str(result_path)],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(json.loads(completed.stdout)["protocol"], "MEITUAN_EVAL_TASK_V2")

    def test_finalize_allows_blocked_task_to_complete_after_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.prepare(root)
            project = root / "project"
            task_path = Path(payload["portableTask"]["taskPath"])
            result_path = Path(payload["portableTask"]["resultPath"])

            result_path.write_text(json.dumps({
                "ok": False, "query": "露营", "blockedAt": "stageB", "error": "needs phase3 retry",
            }, ensure_ascii=False))
            blocked = subprocess.run(
                [sys.executable, str(CLI_PATH), "finalize-evaluate", "--task", str(task_path), "--result", str(result_path)],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(json.loads(blocked.stdout)["status"], "blocked")

            manifest = project / "screenshots-out" / "elements.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}")
            manifest_audit = project / "screenshots-out" / "elements.audit.json"
            manifest_audit.write_text('{"valid": true}')
            eval_result = project / ".artifacts" / "eval-results.json"
            eval_result.parent.mkdir(parents=True)
            eval_result.write_text("[]")
            eval_audit = project / ".artifacts" / "eval-audit.json"
            eval_audit.write_text('{"valid": true}')
            result_path.write_text(json.dumps({
                "ok": True, "query": "露营",
                "stageA": {"elementListPaths": [str(manifest)], "elementAuditPaths": [str(manifest_audit)]},
                "stageB": {"evalResultFile": str(eval_result), "evalAuditFile": str(eval_audit)},
                "stageC": {"evidenceImages": []}, "stageD": {},
                "blockedAt": "", "error": "",
            }, ensure_ascii=False))
            completed = subprocess.run(
                [sys.executable, str(CLI_PATH), "finalize-evaluate", "--task", str(task_path), "--result", str(result_path)],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(json.loads(completed.stdout)["status"], "completed")
            self.assertTrue((task_path.parent / "receipt.blocked-stageB.json").is_file())

    def test_finalize_batch_requires_completed_v3_tasks_and_builds_one_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "phase5-report").symlink_to(PROJECT_DIR / "phase5-report", target_is_directory=True)
            batch_id = "batch-two-queries"
            task_paths = []

            for index, query in enumerate(("咖啡", "火锅"), start=1):
                run_dir = project / "runs" / f"run-{index}"
                run_dir.mkdir(parents=True)
                screenshot = project / "screenshots" / f"{query}_全部_1.png"
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                screenshot.write_bytes(b"image")
                manifest = project / "screenshots-out" / f"elements_{query}_run-{index}.json"
                manifest.parent.mkdir(parents=True, exist_ok=True)
                manifest.write_text(json.dumps({
                    "query": query,
                    "screenshot": str(screenshot),
                    "cards": [{
                        "cardId": "C1",
                        "卡片类型": "商家卡片-文字下挂",
                        "ownershipScope": "business",
                        "businessCode": "dine_in",
                        "regions": [{"name": "标题区", "elements": [{"id": "E1", "内容简述": f"原文:{query}门店"}]}],
                    }],
                }, ensure_ascii=False))
                manifest_audit = manifest.with_name(manifest.stem + ".audit.json")
                manifest_audit.write_text('{"valid": true}')
                result_dir = project / ".artifacts" / "过程文件-评测结果与审计" / batch_id / query / "results"
                result_dir.mkdir(parents=True)
                eval_result = result_dir / f"评测原始结果_{query}_full19.json"
                eval_result.write_text(json.dumps([{
                    "dimension": "phase3-card_or_component-eval",
                    "skill": "eval-8-info-redundancy",
                    "units": [{
                        "tab": "全部",
                        "rating": "优秀",
                        "reason": "未发现问题",
                        "details": {"screenshot": str(screenshot), "evidenceMode": "original-page", "issues": []},
                    }],
                }], ensure_ascii=False))
                eval_audit = result_dir / f"评测结果校验_{query}.json"
                eval_audit.write_text('{"valid": true}')
                result_path = run_dir / "agent-result.json"
                result_path.write_text(json.dumps({
                    "ok": True,
                    "query": query,
                    "stageA": {"elementListPaths": [str(manifest)], "elementAuditPaths": [str(manifest_audit)]},
                    "stageB": {"evalResultFile": str(eval_result), "evalAuditFile": str(eval_audit)},
                    "stageC": {"evidenceImages": []},
                    "stageD": {},
                    "blockedAt": "",
                    "error": "",
                }, ensure_ascii=False))
                task_path = run_dir / "task.json"
                task_path.write_text(json.dumps({
                    "protocol": "MEITUAN_EVAL_TASK_V3",
                    "runId": f"run-{index}",
                    "projectDir": str(project),
                    "workflowArgs": {
                        "query": query,
                        "batchId": batch_id,
                        "reportOutlet": "local_html",
                        "evaluationSelection": {"mode": "full_19"},
                    },
                    "resultPath": str(result_path),
                }, ensure_ascii=False))
                (run_dir / "receipt.json").write_text(json.dumps({
                    "protocol": "MEITUAN_EVAL_TASK_V3",
                    "runId": f"run-{index}",
                    "query": query,
                    "resultPath": str(result_path),
                    "status": "completed",
                }))
                task_paths.append(task_path)

            command = [
                sys.executable, str(CLI_PATH), "finalize-batch",
                "--project-dir", str(project),
                "--batch-id", batch_id,
                "--expected-business-tabs", "dine_in",
            ]
            for task_path in task_paths:
                command.extend(["--task", str(task_path)])
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
            payload = json.loads(completed.stdout)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["queries"], ["咖啡", "火锅"])
            self.assertTrue(Path(payload["reportPath"]).is_file())
            self.assertTrue(Path(payload["datasetPath"]).is_file())

            (task_paths[1].parent / "receipt.json").write_text(json.dumps({
                "protocol": "MEITUAN_EVAL_TASK_V3",
                "runId": "run-2",
                "query": "火锅",
                "resultPath": str(task_paths[1].parent / "agent-result.json"),
                "status": "blocked",
                "blockedAt": "stageA",
                "error": "phase2 needs review",
            }, ensure_ascii=False))
            partial = command + [
                "--output", str(project / "reports" / "partial.html"),
                "--dataset-output", str(project / "reports" / ".partial.json"),
            ]
            partial_completed = subprocess.run(partial, check=True, capture_output=True, text=True)
            partial_payload = json.loads(partial_completed.stdout)
            self.assertEqual(partial_payload["queries"], ["咖啡"])
            self.assertEqual(partial_payload["skippedTasks"][0]["query"], "火锅")
            self.assertIn("未纳入报告：火锅", Path(partial_payload["reportPath"]).read_text())
