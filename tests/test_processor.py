import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from kc_logo_cleaner.geometry import calculate_mask_box
from kc_logo_cleaner.models import MaskConfig
from kc_logo_cleaner.processor import collect_images, process_batch, process_image


class ProcessorTests(unittest.TestCase):
    def create_test_image(self, path: Path, size: tuple[int, int] = (800, 450)) -> None:
        image = Image.new("RGB", size, "#3478A5")
        draw = ImageDraw.Draw(image)
        for y in range(size[1]):
            color = (40 + y // 8, 100 + y // 12, 145 + y // 16)
            draw.line((0, y, size[0], y), fill=color)
        box = calculate_mask_box(size[0], size[1], MaskConfig())
        draw.text((box.left + 2, box.top + 2), "✦", fill="white")
        image.save(path)

    def test_process_image_preserves_dimensions_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "ảnh nguồn.png"
            output = root / "kết quả" / "ảnh nguồn.png"
            self.create_test_image(source)
            before = source.read_bytes()

            result = process_image(source, output, MaskConfig())

            self.assertEqual(result.status, "completed")
            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(output.exists())
            with Image.open(output) as cleaned:
                self.assertEqual(cleaned.size, (800, 450))

    def test_pixels_outside_mask_are_unchanged_for_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            output = root / "output.png"
            self.create_test_image(source)
            process_image(source, output, MaskConfig(feather_radius=0))
            original = np.asarray(Image.open(source).convert("RGB"))
            cleaned = np.asarray(Image.open(output).convert("RGB"))
            self.assertTrue(np.array_equal(original[:200, :400], cleaned[:200, :400]))

    def test_texture_patch_changes_logo_region_without_resizing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.png"
            output = root / "output.png"
            self.create_test_image(source, size=(1376, 768))
            original = np.asarray(Image.open(source).convert("RGB"))

            result = process_image(source, output, MaskConfig())
            cleaned = np.asarray(Image.open(output).convert("RGB"))
            box = calculate_mask_box(1376, 768, MaskConfig())

            self.assertEqual(result.status, "completed")
            self.assertEqual(cleaned.shape, original.shape)
            self.assertFalse(
                np.array_equal(
                    original[box.top : box.bottom, box.left : box.right],
                    cleaned[box.top : box.bottom, box.left : box.right],
                )
            )

    def test_batch_preserves_subfolders_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = source / "KC_Logo_Cleaned"
            nested = source / "scene-set"
            nested.mkdir(parents=True)
            self.create_test_image(source / "scene-001.png")
            self.create_test_image(nested / "scene-002.png")

            results = process_batch(source, output, MaskConfig(), recursive=True)

            self.assertEqual(len(results), 2)
            self.assertTrue((output / "scene-001.png").exists())
            self.assertTrue((output / "scene-set" / "scene-002.png").exists())
            report = json.loads((output / "processing-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["completed"], 2)
            self.assertEqual(len(collect_images(source, output, recursive=True)), 2)


if __name__ == "__main__":
    unittest.main()
