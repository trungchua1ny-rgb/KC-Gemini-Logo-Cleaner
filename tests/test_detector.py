import unittest

import numpy as np

from kc_logo_cleaner.detector import _sparkle_template, detect_logo_box
from kc_logo_cleaner.geometry import calculate_mask_box
from kc_logo_cleaner.models import MaskConfig


class LogoDetectorTests(unittest.TestCase):
    def test_refines_mask_to_a_shifted_visible_sparkle(self) -> None:
        image = np.full((768, 1376, 3), (70, 115, 125), dtype=np.uint8)
        expected_center = (1292, 651)
        template = _sparkle_template(57)
        logo = np.clip(template * 175, 0, 255).astype(np.uint8)
        top = expected_center[1] - logo.shape[0] // 2
        left = expected_center[0] - logo.shape[1] // 2
        for channel in range(3):
            region = image[top : top + logo.shape[0], left : left + logo.shape[1], channel]
            image[top : top + logo.shape[0], left : left + logo.shape[1], channel] = np.maximum(region, logo)

        fallback = calculate_mask_box(1376, 768, MaskConfig())
        detected, confidence = detect_logo_box(image, fallback)
        detected_center = ((detected.left + detected.right) // 2, (detected.top + detected.bottom) // 2)
        self.assertLessEqual(abs(detected_center[0] - expected_center[0]), 3)
        self.assertLessEqual(abs(detected_center[1] - expected_center[1]), 3)
        self.assertGreater(confidence, 0.5)

    def test_uniform_image_keeps_calibrated_fallback(self) -> None:
        image = np.full((768, 1376, 3), 230, dtype=np.uint8)
        fallback = calculate_mask_box(1376, 768, MaskConfig())
        detected, confidence = detect_logo_box(image, fallback)
        self.assertEqual(detected, fallback)
        self.assertLess(confidence, 0.3)


if __name__ == "__main__":
    unittest.main()
