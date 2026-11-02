from __future__ import annotations

import unittest

from span_app.widgets import blend_color


class BlendColorTests(unittest.TestCase):
    def test_endpoints_are_preserved(self) -> None:
        self.assertEqual(blend_color("#123456", "#abcdef", 0.0), "#123456")
        self.assertEqual(blend_color("#123456", "#abcdef", 1.0), "#abcdef")

    def test_amount_is_clamped(self) -> None:
        self.assertEqual(blend_color("#123456", "#abcdef", -5), "#123456")
        self.assertEqual(blend_color("#123456", "#abcdef", 5), "#abcdef")

    def test_midpoint_blends_each_channel(self) -> None:
        self.assertEqual(blend_color("#000000", "#ffffff", 0.5), "#808080")
        self.assertEqual(blend_color("#ff0000", "#0000ff", 0.5), "#800080")


if __name__ == "__main__":
    unittest.main()
