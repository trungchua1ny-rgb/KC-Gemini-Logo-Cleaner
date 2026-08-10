import unittest

import numpy as np

from kc_logo_cleaner.geometry import MaskBox
from kc_logo_cleaner.lama_engine import _context_crop, _soft_composite


class LamaEngineTests(unittest.TestCase):
    def test_context_crop_stays_inside_image_and_contains_logo(self) -> None:
        box = MaskBox(left=1237, top=629, right=1321, bottom=713)
        left, top, right, bottom = _context_crop(1376, 768, box)
        self.assertEqual(right - left, bottom - top)
        self.assertGreaterEqual(right - left, 512)
        self.assertLessEqual(left, box.left)
        self.assertLessEqual(top, box.top)
        self.assertGreaterEqual(right, box.right)
        self.assertGreaterEqual(bottom, box.bottom)

    def test_composite_keeps_every_pixel_outside_mask(self) -> None:
        original = np.full((30, 40, 3), 25, dtype=np.uint8)
        generated = np.full((30, 40, 3), 220, dtype=np.uint8)
        mask = np.zeros((30, 40), dtype=np.uint8)
        mask[10:20, 15:25] = 255
        result = _soft_composite(original, generated, mask, feather_radius=0)
        self.assertTrue(np.array_equal(result[:10], original[:10]))
        self.assertTrue(np.array_equal(result[:, :15], original[:, :15]))
        self.assertTrue(np.array_equal(result[10:20, 15:25], generated[10:20, 15:25]))


if __name__ == "__main__":
    unittest.main()
