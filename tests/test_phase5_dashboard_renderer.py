from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "phase5-report" / "dashboard_renderer.py"


def load_renderer():
    spec = importlib.util.spec_from_file_location("phase5_dashboard_renderer", RENDERER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Phase5DashboardRendererTest(unittest.TestCase):
    def test_renders_reference_layout_without_changing_issue_facts(self) -> None:
        renderer = load_renderer()
        data = {
            "generatedAt": "2026-08-26",
            "queryCount": 2,
            "batch": "验证批次",
            "businesses": [
                {
                    "businessCode": "dine_in",
                    "businessName": "到餐",
                    "issueCount": 1,
                    "tracking": {"newIssueCount": 1, "resolvedIssueCount": 0},
                }
            ],
            "groups": [
                {
                    "businessCode": "dine_in",
                    "level": "component",
                    "levelName": "组件/卡片",
                    "metricName": "信息冗余",
                    "evidence": [
                        {
                            "rating": "不达标",
                            "priority": "P1",
                            "query": "火锅",
                            "tab": "全部",
                            "elementLabel": "商家信息区",
                            "evidenceImage": "/tmp/firepot_evidence.png",
                            "finding": {
                                "observableFact": "商家信息区重复展示配送文案",
                                "ruleOrThreshold": "同类信息只展示一次",
                                "verdictReason": "重复信息占用首屏空间",
                                "userImpact": "用户阅读时需要重复确认",
                            },
                            "recommendation": "合并重复配送文案，并保留一次可见的履约说明。",
                        }
                    ],
                }
            ],
        }

        html = renderer.render_dashboard(data)

        self.assertNotIn("class='topbar'", html)
        self.assertIn("class='summary-card'", html)
        self.assertEqual(html.count("class='donut-block'"), 4)
        self.assertIn(".evidence-link,.evidence-link img,.evidence-empty{display:block;width:240px;height:180px", html)
        self.assertIn("商家信息区重复展示配送文案，评级为不达标。用户阅读时需要重复确认。", html)
        self.assertIn("合并重复配送文案，并保留一次可见的履约说明。", html)
        self.assertIn("data-detail-tab='dine_in-issue'", html)

