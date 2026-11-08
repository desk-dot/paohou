import copy
import json
from pathlib import Path
import unittest

from analysis_tools import calculate_metrics, compare_runs, format_pace, pace_seconds, validate_record

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

    def test_compare_identical_runs_and_missing_field(self):
        result = compare_runs([DEMO, copy.deepcopy(DEMO)])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["comparisons"]["average_pace"][0],
                         {"pair": [1, 2], "delta": 0, "verdict": "close"})
        self.assertEqual(result["comparisons"]["step_length_m"][0]["verdict"], "unknown")

    def test_compare_tolerance_boundary_and_outside(self):
        base = {"total_distance_km": 1, "total_duration_s": 300,
                "cadence_spm": 100, "step_length_m": 1, "elevation_gain_m": 0}
        at_boundary = dict(base, total_duration_s=310)
        outside = dict(base, total_duration_s=311)
        # Each run has a 5 s/km minimum pace tolerance; equality is close.
        self.assertEqual(compare_runs([base, at_boundary])["comparisons"]["average_pace"][0]["verdict"], "close")
        self.assertEqual(compare_runs([base, outside])["comparisons"]["average_pace"][0]["verdict"], "different")
        self.assertEqual(compare_runs([base, at_boundary])["runs"][0]["tolerances"]["elevation_gain_m"], 1)

    def test_compare_count_and_invalid_record_boundaries(self):
        for runs in ([DEMO], [DEMO] * 21, "not-a-list"):
            with self.subTest(size=len(runs)), self.assertRaises(ValueError):
                compare_runs(runs)
        self.assertEqual(compare_runs([DEMO] * 20)["count"], 20)
        with self.assertRaisesRegex(ValueError, "总距离"):
            compare_runs([DEMO, {"total_distance_km": -1, "total_duration_s": 300}])

    def test_compare_mixed_scope_is_flagged(self):
        split_only = copy.deepcopy(DEMO)
        split_only["total_duration_s"] = None
        result = compare_runs([DEMO, split_only])
        self.assertTrue(any("统计口径不同" in note for note in result["comparability_notes"]))


if __name__ == "__main__":
    unittest.main()
