import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from review_file import main

DEMO = Path(__file__).parents[1] / "examples/demo.json"


class ReviewFileTests(unittest.TestCase):
    def test_write_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.md"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([str(DEMO), "--output", str(target)])
            self.assertEqual(code, 0)
            text = target.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# 跑步复盘"))
            self.assertIn("平均配速：6:12 /km", text)
            self.assertIn("已保存", out.getvalue())

    def test_existing_target_survives_check_write_race(self):
        """存在性检查通过后目标才被其他进程创建：x 模式兜底，拒绝覆盖。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.md"
            target.write_text("原始内容", encoding="utf-8")
            errors = io.StringIO()
            with mock.patch.object(Path, "exists", return_value=False), \
                    contextlib.redirect_stderr(errors):
                code = main([str(DEMO), "--output", str(target)])
            self.assertEqual(code, 1)
            self.assertIn("拒绝覆盖", errors.getvalue())
            self.assertEqual(target.read_text(encoding="utf-8"), "原始内容")


if __name__ == "__main__":
    unittest.main()
