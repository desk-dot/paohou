from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "streamlit_app.py")


class AppTests(unittest.TestCase):
    def test_demo_confirmation_and_stale_report(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        self.assertFalse(app.exception)
        app.button(key="demo").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[1].value, "6:12 /km")
        self.assertTrue(app.button(key="local").disabled)
        confirm = next(w for w in app.checkbox if w.key.startswith("confirmed_"))
        confirm.check().run()
        app.button(key="local").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("跑步复盘（本地规则版）" in m.value for m in app.markdown))
        distance = next(w for w in app.text_input if w.key and w.key.startswith("total_distance_km_"))
        distance.set_value("3").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key="local").disabled)
        self.assertFalse(any("跑步复盘（本地规则版）" in m.value for m in app.markdown))

    def test_invalid_distance_shows_error(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        app.button(key="demo").click().run()
        next(w for w in app.text_input if w.key and w.key.startswith("total_distance_km_")).set_value("NaN").run()
        self.assertTrue(app.error)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
