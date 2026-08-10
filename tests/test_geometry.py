import unittest

from kc_logo_cleaner.geometry import calculate_mask_box
from kc_logo_cleaner.models import MaskConfig


class MaskGeometryTests(unittest.TestCase):
    def test_default_mask_is_in_bottom_right(self) -> None:
        box = calculate_mask_box(1920, 1080, MaskConfig())
        self.assertGreater(box.left, 1920 * 0.89)
        self.assertGreater(box.top, 1080 * 0.8)
        self.assertLessEqual(box.right, 1920)
        self.assertLessEqual(box.bottom, 1080)

    def test_mask_scales_with_resolution(self) -> None:
        config = MaskConfig()
        small = calculate_mask_box(1024, 1024, config)
        large = calculate_mask_box(2048, 2048, config)
        self.assertAlmostEqual(large.width / small.width, 2.0, delta=0.1)
        self.assertAlmostEqual(large.height / small.height, 2.0, delta=0.1)

    def test_preset_matches_calibrated_gemini_output(self) -> None:
        box = calculate_mask_box(1376, 768, MaskConfig())
        self.assertEqual(box, type(box)(left=1237, top=629, right=1321, bottom=713))

    def test_invalid_config_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_mask_box(1920, 1080, MaskConfig(width_percent=40))


if __name__ == "__main__":
    unittest.main()
