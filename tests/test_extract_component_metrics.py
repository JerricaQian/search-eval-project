from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "phase3-evaluation-officer" / "scripts" / "extract_component_metrics.py"


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("extract_component_metrics_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class ExtractComponentMetricsTest(unittest.TestCase):
    def test_seven_color_bins_use_the_shared_taxonomy(self) -> None:
        module = load_module()
        from color_taxonomy import HUE7_BINS
        self.assertEqual(module.HUE_FAMILIES, list(HUE7_BINS))

    def test_seven_color_hue_mapping_merges_yellow_green_and_magenta(self) -> None:
        module = load_module()
        self.assertEqual(module.hue_family(75), "green")
        self.assertEqual(module.hue_family(310), "purple")
        self.assertEqual(module.hue_family(175), "cyan")

    def test_hierarchy_gap_threshold_uses_calibrated_width_scale(self) -> None:
        module = load_module()
        self.assertEqual(module.hierarchy_glyph_gap_threshold(1224), 6)
        self.assertEqual(module.hierarchy_glyph_gap_threshold(1206), 6)
        self.assertEqual(module.hierarchy_glyph_gap_threshold(612), 3)

    def test_hierarchy_only_measurement_uses_json_colour_and_glyph_pixels(self) -> None:
        module = load_module()
        import numpy as np

        image = np.full((80, 160, 3), 255, dtype=np.uint8)
        image[12:20, 10:80] = [20, 20, 20]
        card = {
            "cardId": "C1",
            "卡片类型": "酒店卡片",
            "coord": [0, 0, 160, 80],
            "regions": [{
                "name": "title",
                "elements": [{
                    "id": "T1",
                    "元素类型": "文本",
                    "内容简述": "原文:酒店标题",
                    "坐标": [8, 8, 80, 20],
                    "textFacts": {"rawText": "酒店标题", "semanticRole": "title"},
                    "visual": {"textColor": "#FF6600", "backgroundColor": "#FFFFFF"},
                }],
            }],
        }
        result = module.analyse_hierarchy_card(image, card)
        hierarchy = result["hierarchyMeasurement"]
        self.assertEqual(hierarchy["calibrationProfile"], "phase3.hierarchy-glyph.v1")
        self.assertEqual(hierarchy["glyphHeightGapThresholdPx"], 3)
        self.assertEqual(len(hierarchy["weightBlocks"]), 1)
        self.assertTrue(hierarchy["weightBlocks"][0]["chromatic"])
        self.assertGreater(hierarchy["weightBlocks"][0]["glyphHeightPx"], 0)

    def test_icon_measurement_traverses_atoms_without_visual_inventory(self) -> None:
        module = load_module()
        import numpy as np
        elements = [
            {"id": "kept", "坐标": [0, 0, 20, 20], "visual": {"entityKind": "icon", "visualStatus": "confirmed"}},
            {"id": "uncertain", "坐标": [30, 0, 20, 20], "visual": {"entityKind": "icon", "visualStatus": "uncertain"}},
        ]
        image = np.full((40, 60, 3), 255, dtype=np.uint8)
        result = module.derive_icon_styles(image, elements, np.zeros((40, 60), dtype=np.uint8))
        self.assertEqual([item["id"] for item in result["iconEntities"]], ["kept"])
        self.assertFalse(result["measurementComplete"])
        self.assertEqual(result["unmeasuredAtomicIconIds"], ["kept"])
        self.assertEqual(result["countSource"], "phase3.pixel_measurement_within_phase2_icon_atoms")

    def test_component_scope_excludes_navigation_and_filter_modules(self) -> None:
        module = load_module()
        records = module.excluded_page_modules({"pageFacts": {"modules": [
            {"id": "M1", "moduleType": "tab", "coord": [0, 0, 100, 40]},
            {"id": "M2", "moduleType": "business_image_filter", "coord": [0, 40, 100, 80]},
            {"id": "M3", "moduleType": "sort_filter", "coord": [0, 120, 100, 40]},
        ]}})
        self.assertEqual([record["moduleType"] for record in records], ["tab", "business_image_filter", "sort_filter"])

    def test_primary_price_and_rating_are_excluded_before_style_key_generation(self) -> None:
        module = load_module()

        def element(element_id: str, text: str, role: str) -> dict:
            return {
                "id": element_id,
                "元素类型": "文本",
                "内容简述": f"原文:{text}",
                "坐标": [0, 0, 30, 20],
                "textFacts": {"rawText": text, "semanticRole": role},
                "visual": {"entityKind": "text", "visualStatus": "confirmed"},
            }

        self.assertEqual(module.primary_field_exclusion(element("R1", "4.9分", "rating")), "核心评分值不是标签")
        self.assertEqual(module.primary_field_exclusion(element("P1", "¥375起", "price")), "主价格不是标签")
        self.assertIsNone(module.primary_field_exclusion(element("P2", "夏日特惠", "price")))
        self.assertIsNone(module.primary_field_exclusion(element("R2", "服务很好非常喜欢", "recommendation")))

    def test_whole_card_scan_counts_coloured_auxiliary_text_and_deduplicates_style_keys(self) -> None:
        module = load_module()
        import numpy as np

        image = np.full((180, 240, 3), 255, dtype=np.uint8)

        def element(element_id: str, text: str, role: str, box: list[int]) -> dict:
            x, y, width, height = box
            image[y + height // 2 - 1:y + height // 2 + 1, x:x + width] = [10, 50, 180]
            return {
                "id": element_id,
                "元素类型": "文本",
                "内容简述": f"原文:{text}",
                "坐标": box,
                "isExcluded": False,
                "textFacts": {"rawText": text, "semanticRole": role},
                "visual": {
                    "entityKind": "text",
                    "visualStatus": "confirmed",
                    "containerShape": "none",
                    "graphicAssistRole": "none",
                },
            }

        card = {
            "cardId": "C1",
            "卡片类型": "酒店卡片",
            "coord": [0, 0, 240, 180],
            "regions": [
                {"name": "title", "coord": [0, 0, 100, 30], "elements": [element("T1", "彩色标题", "title", [5, 5, 80, 20])]},
                {"name": "rating_and_reason", "coord": [0, 40, 220, 30], "elements": [
                    element("R1", "4.9分", "rating", [5, 45, 50, 20]),
                    element("R2", "服务很好非常喜欢", "recommendation", [65, 45, 130, 20]),
                ]},
                {"name": "price", "coord": [0, 80, 220, 70], "elements": [
                    element("P1", "¥375起", "price", [5, 85, 60, 20]),
                    element("P2", "夏日特惠", "promotion", [75, 85, 65, 20]),
                    element("P3", "立享9.3折", "promotion", [75, 115, 65, 20]),
                ]},
            ],
        }
        result = module.analyse_card(
            image,
            card,
            np.zeros((180, 240), dtype=np.uint8),
            np.full((180, 240), 255, dtype=np.uint8),
        )

        self.assertEqual(result["expectedRegions"], ["title", "rating_and_reason", "price"])
        self.assertEqual(result["scannedRegions"], result["expectedRegions"])
        self.assertEqual(result["unscannedRegions"], [])
        decisions = {item["elementId"]: item for item in result["candidateLedger"]}
        self.assertEqual(decisions["T1"]["decision"], "excluded")
        self.assertEqual(decisions["R1"]["decision"], "excluded")
        self.assertEqual(decisions["P1"]["decision"], "excluded")
        self.assertEqual(decisions["R2"]["decision"], "included_tag")
        self.assertEqual(decisions["P2"]["decision"], "included_tag")
        self.assertEqual(decisions["P2"]["styleKey"], decisions["P3"]["styleKey"])
        self.assertEqual(result["tagStyleCount"], 2)
        self.assertTrue(all(len(group["styleKey"].split("|")) == 5 for group in result["tagStyleGroups"]))

    def test_uncovered_compact_photo_overlay_requests_phase2_review(self) -> None:
        module = load_module()
        import numpy as np

        image = np.full((100, 100, 3), 180, dtype=np.uint8)
        image[2:22, 2:32] = [20, 20, 230]
        media = [{"id": "M1", "坐标": [0, 0, 100, 100]}]

        hits = module.detect_media_overlay_candidates(image, media, [])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["decision"], "phase2_review_required")
        self.assertEqual(hits[0]["mediaElementId"], "M1")

        covered = module.detect_media_overlay_candidates(image, media, [[0, 0, 40, 30]])
        self.assertEqual(covered, [])


if __name__ == "__main__":
    unittest.main()
