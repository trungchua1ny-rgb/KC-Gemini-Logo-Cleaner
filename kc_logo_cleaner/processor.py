from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import cv2
import numpy as np
from PIL import Image, ImageOps

from .detector import detect_logo_box
from .geometry import MaskBox, calculate_mask_box
from .lama_engine import LamaModelError, lama_inpaint
from .models import MaskConfig, ProcessingResult


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
ProgressCallback = Callable[[int, int, Path, ProcessingResult | None], None]
CancelCallback = Callable[[], bool]


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def collect_images(source_dir: Path, output_dir: Path | None = None, recursive: bool = True) -> list[Path]:
    source = source_dir.resolve()
    if not source.is_dir():
        raise ValueError("Thư mục nguồn không tồn tại.")

    output = output_dir.resolve() if output_dir else None
    iterator: Iterable[Path] = source.rglob("*") if recursive else source.iterdir()
    images: list[Path] = []

    for path in iterator:
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if output and is_relative_to(path, output):
            continue
        images.append(path)

    return sorted(images, key=lambda item: str(item).casefold())


def create_mask(width: int, height: int, box: MaskBox, config: MaskConfig) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    if config.shape == "gemini-sparkle":
        center_x = (box.left + box.right) / 2
        center_y = (box.top + box.bottom) / 2
        half_width = box.width / 2
        half_height = box.height / 2
        normalized_points = (
            (0.00, -1.00),
            (0.17, -0.27),
            (1.00, 0.00),
            (0.17, 0.27),
            (0.00, 1.00),
            (-0.17, 0.27),
            (-1.00, 0.00),
            (-0.17, -0.27),
        )
        points = np.array(
            [
                [round(center_x + x * half_width), round(center_y + y * half_height)]
                for x, y in normalized_points
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(mask, [points], 255)
        dilation = max(1, round(min(width, height) * 0.0025))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation * 2 + 1, dilation * 2 + 1))
        return cv2.dilate(mask, kernel, iterations=1)

    if config.shape == "ellipse":
        center = ((box.left + box.right) // 2, (box.top + box.bottom) // 2)
        axes = (max(1, box.width // 2), max(1, box.height // 2))
        cv2.ellipse(mask, center, axes, 0, 0, 360, 255, thickness=-1)
        return mask

    radius = max(2, min(box.width, box.height) // 4)
    cv2.rectangle(
        mask,
        (box.left + radius, box.top),
        (box.right - radius, box.bottom),
        255,
        thickness=-1,
    )
    cv2.rectangle(
        mask,
        (box.left, box.top + radius),
        (box.right, box.bottom - radius),
        255,
        thickness=-1,
    )
    for center in (
        (box.left + radius, box.top + radius),
        (box.right - radius, box.top + radius),
        (box.left + radius, box.bottom - radius),
        (box.right - radius, box.bottom - radius),
    ):
        cv2.circle(mask, center, radius, 255, thickness=-1)
    return mask


def texture_patch_fill(rgb_array: np.ndarray, box: MaskBox, feather_radius: int) -> np.ndarray:
    """Replace the logo box with the best matching nearby texture patch.

    Gemini places the visible mark over the final pixels. Copying a nearby
    patch whose surrounding border matches the destination preserves lines and
    textures better than diffusion-style OpenCV inpainting for this small,
    fixed corner region.
    """
    source = rgb_array.astype(np.float32)
    height, width = source.shape[:2]
    left, top = box.left, box.top
    patch_width = box.width
    patch_height = box.height
    gray = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY).astype(np.float32)

    scale = max(0.5, min(width / 1376, height / 768))
    gap = max(3, round(8 * scale))
    ring = max(2, round(5 * scale))
    step = max(2, round(4 * scale))
    search_x = min(round(width * 0.28), max(100, round(320 * scale)))
    search_y = min(round(height * 0.45), max(100, round(320 * scale)))

    def boundary_strips(array: np.ndarray, x: int, y: int) -> tuple[np.ndarray, ...]:
        return (
            array[y - gap - ring : y - gap, x : x + patch_width],
            array[y + patch_height + gap : y + patch_height + gap + ring, x : x + patch_width],
            array[y : y + patch_height, x - gap - ring : x - gap],
            array[y : y + patch_height, x + patch_width + gap : x + patch_width + gap + ring],
        )

    if (
        left - gap - ring < 0
        or top - gap - ring < 0
        or left + patch_width + gap + ring >= width
        or top + patch_height + gap + ring >= height
    ):
        raise ValueError("Ảnh quá nhỏ để tự động tìm vùng nền thay thế.")

    target_strips = boundary_strips(gray, left, top)
    best_score = float("inf")
    best_position: tuple[int, int] | None = None

    for offset_y in range(-search_y, search_y // 2 + 1, step):
        for offset_x in range(-search_x, search_x // 2 + 1, step):
            if abs(offset_x) < patch_width + gap and abs(offset_y) < patch_height + gap:
                continue
            candidate_x = left + offset_x
            candidate_y = top + offset_y
            if (
                candidate_x - gap - ring < 0
                or candidate_y - gap - ring < 0
                or candidate_x + patch_width + gap + ring >= width
                or candidate_y + patch_height + gap + ring >= height
            ):
                continue

            candidate_strips = boundary_strips(gray, candidate_x, candidate_y)
            score = sum(
                float(np.mean((target - candidate) ** 2))
                for target, candidate in zip(target_strips, candidate_strips)
            )
            score *= 1 + 0.00035 * (abs(offset_x) + abs(offset_y))
            if score < best_score:
                best_score = score
                best_position = (candidate_x, candidate_y)

    if best_position is None:
        raise ValueError("Không tìm thấy vùng nền phù hợp để thay logo.")

    candidate_x, candidate_y = best_position
    replacement = source[
        candidate_y : candidate_y + patch_height,
        candidate_x : candidate_x + patch_width,
    ]
    destination = source[top : top + patch_height, left : left + patch_width]

    edge = max(3, feather_radius * 2 + 2)
    y_grid, x_grid = np.mgrid[0:patch_height, 0:patch_width]
    alpha = np.minimum.reduce(
        (
            np.clip((x_grid + 1) / edge, 0, 1),
            np.clip((patch_width - x_grid) / edge, 0, 1),
            np.clip((y_grid + 1) / edge, 0, 1),
            np.clip((patch_height - y_grid) / edge, 0, 1),
        )
    )[:, :, np.newaxis]

    result = source.copy()
    result[top : top + patch_height, left : left + patch_width] = (
        replacement * alpha + destination * (1.0 - alpha)
    )
    return np.clip(result, 0, 255).astype(np.uint8)


def clean_array(rgb_array: np.ndarray, config: MaskConfig) -> tuple[np.ndarray, MaskBox]:
    if rgb_array.ndim != 3 or rgb_array.shape[2] != 3:
        raise ValueError("Ảnh đầu vào phải ở định dạng RGB.")

    height, width = rgb_array.shape[:2]
    nominal_box = calculate_mask_box(width, height, config)
    box, confidence = detect_logo_box(rgb_array, nominal_box)
    # A clearly detected sparkle gets a shape-aware mask, so surrounding
    # object pixels are preserved. Low-confidence cases use the larger safe
    # rounded mask at the calibrated position.
    mask_config = replace(config, shape="gemini-sparkle") if confidence >= 0.30 else config
    mask = create_mask(width, height, box, mask_config)
    if config.method == "lama-ai":
        try:
            return lama_inpaint(rgb_array, mask, box, config.feather_radius), box
        except LamaModelError:
            # The offline fallback still returns a usable result when the
            # model cannot be downloaded or initialized.
            try:
                return texture_patch_fill(rgb_array, box, config.feather_radius), box
            except ValueError:
                pass
    if config.method == "texture-patch":
        try:
            return texture_patch_fill(rgb_array, box, config.feather_radius), box
        except ValueError:
            # Very small images may not have enough surrounding pixels. Fall
            # back to the lightweight local inpainting engine.
            pass

    bgr = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    method = cv2.INPAINT_NS if config.method == "navier-stokes" else cv2.INPAINT_TELEA
    repaired = cv2.inpaint(bgr, mask, config.inpaint_radius, method)

    if config.feather_radius > 0:
        kernel = config.feather_radius * 2 + 1
        softened = cv2.GaussianBlur(mask, (kernel, kernel), 0).astype(np.float32) / 255.0
        alpha = softened[:, :, np.newaxis]
        repaired = np.clip(repaired * alpha + bgr * (1.0 - alpha), 0, 255).astype(np.uint8)

    return cv2.cvtColor(repaired, cv2.COLOR_BGR2RGB), box


def load_image(path: Path) -> tuple[Image.Image, dict[str, object]]:
    with Image.open(path) as opened:
        metadata: dict[str, object] = {}
        if "icc_profile" in opened.info:
            metadata["icc_profile"] = opened.info["icc_profile"]
        exif = opened.getexif()
        if exif:
            # Pixels are physically rotated below, so the old orientation tag
            # must not rotate the saved output a second time.
            exif.pop(274, None)
            metadata["exif"] = exif.tobytes()
        transposed = ImageOps.exif_transpose(opened)
        return transposed.copy(), metadata


def save_image(image: Image.Image, destination: Path, metadata: dict[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.processing{destination.suffix}")
    extension = destination.suffix.lower()
    options: dict[str, object] = {}

    if metadata.get("icc_profile"):
        options["icc_profile"] = metadata["icc_profile"]
    if metadata.get("exif") and extension in {".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        options["exif"] = metadata["exif"]

    if extension in {".jpg", ".jpeg"}:
        options.update({"quality": 96, "subsampling": 0, "optimize": True})
        image = image.convert("RGB")
    elif extension == ".webp":
        options.update({"quality": 96, "method": 6})
    elif extension == ".png":
        options.update({"compress_level": 6})
    elif extension in {".tif", ".tiff"}:
        options.update({"compression": "tiff_lzw"})

    try:
        image.save(temporary, **options)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def process_image(source: Path, destination: Path, config: MaskConfig) -> ProcessingResult:
    try:
        original, metadata = load_image(source)
        alpha = original.getchannel("A") if "A" in original.getbands() else None
        rgb_array = np.asarray(original.convert("RGB"), dtype=np.uint8)
        cleaned_array, _ = clean_array(rgb_array, config)
        cleaned = Image.fromarray(cleaned_array)
        if alpha is not None:
            cleaned.putalpha(alpha)
        save_image(cleaned, destination, metadata)
        return ProcessingResult(
            source=source,
            output=destination,
            status="completed",
            width=cleaned.width,
            height=cleaned.height,
        )
    except Exception as error:  # keep a failed file from stopping the whole batch
        return ProcessingResult(source=source, output=None, status="failed", error=str(error))


def process_batch(
    source_dir: Path,
    output_dir: Path,
    config: MaskConfig,
    recursive: bool = True,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> list[ProcessingResult]:
    config.validate()
    source = source_dir.resolve()
    output = output_dir.resolve()
    if source == output:
        raise ValueError("Thư mục kết quả phải khác thư mục nguồn.")

    images = collect_images(source, output, recursive)
    results: list[ProcessingResult] = []
    total = len(images)

    for index, path in enumerate(images, start=1):
        if cancelled and cancelled():
            result = ProcessingResult(source=path, output=None, status="cancelled")
            results.append(result)
            if progress:
                progress(index, total, path, result)
            break

        relative = path.relative_to(source)
        destination = output / relative
        result = process_image(path, destination, config)
        results.append(result)
        if progress:
            progress(index, total, path, result)

    write_report(output, source, config, results)
    return results


def write_report(
    output_dir: Path,
    source_dir: Path,
    config: MaskConfig,
    results: list[ProcessingResult],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "processing-report.json"
    payload = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceDirectory": str(source_dir),
        "outputDirectory": str(output_dir),
        "config": config.to_dict(),
        "summary": {
            "total": len(results),
            "completed": sum(item.status == "completed" for item in results),
            "failed": sum(item.status == "failed" for item in results),
            "cancelled": sum(item.status == "cancelled" for item in results),
        },
        "files": [item.to_dict() for item in results],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path
