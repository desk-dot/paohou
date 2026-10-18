import copy
import json
from pathlib import Path
import unittest

from analysis_tools import calculate_metrics, format_pace, pace_seconds, validate_record

DEMO = json.loads((Path(__file__).parents[1] / "examples/demo.json").read_text(encoding="utf-8"))


class AnalysisTests(unittest.TestCase):
    def test_weighted_pace_and_partial_final_kilometer(self):
        raw = copy.deepcopy(DEMO)
        raw["total_duration_s"] = None
        metrics = calculate_metrics(validate_record(raw))
        self.assertEqual(metrics["duration_s"], 930)
        self.assertEqual(metrics["distance_km"], 2.5)
        self.assertEqual(metrics["average_pace"], "6:12")
        self.assertAlmostEqual(metrics["second_minus_first_half_s_per_km"], 16)

    def test_missing_gain_does_not_become_zero(self):
        raw = copy.deepcopy(DEMO)
        raw["elevation_gain_m"] = None
        metrics = calculate_metrics(validate_record(raw))
        self.assertIsNone(metrics["elevation_gain_m"])
        self.assertTrue(any("爬升缺失" in x for x in metrics["warnings"]))

    def test_mismatched_splits_preserve_full_totals(self):
        raw = copy.deepcopy(DEMO)
        raw["total_distance_km"] = 5
        raw["total_duration_s"] = 1800
        metrics = calculate_metrics(validate_record(raw))
        self.assertEqual(metrics["average_pace"], "6:00")
        self.assertTrue(any("距离不一致" in x for x in metrics["warnings"]))

    def test_summary_only(self):
        metrics = calculate_metrics(validate_record({"total_distance_km": 5, "total_duration_s": 1800}))
        self.assertEqual(metrics["average_pace"], "6:00")
        self.assertIsNone(metrics["second_minus_first_half_s_per_km"])

    def test_no_mixing_partial_summary_with_split_totals(self):
        metrics = calculate_metrics(validate_record({"total_distance_km": 5, "splits": [{"distance_km": 1, "pace": "6:00"}]}))
        self.assertEqual(metrics["distance_km"], 1)
        self.assertEqual(metrics["average_pace"], "6:00")

    def test_bad_values_rejected(self):
        for value in [0, -1, True, float("nan"), float("inf"), "abc"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_record({"total_distance_km": value, "total_duration_s": 1800})
        for value in ["6:60", "-1:00", "0:00", None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                pace_seconds(value)

    def test_keep_pace_and_rounding(self):
        self.assertEqual(pace_seconds('6′05″'), 365)
        self.assertEqual(format_pace(359.9), "6:00")


if __name__ == "__main__":
    unittest.main()
