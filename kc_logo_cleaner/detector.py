from __future__ import annotations

import cv2
import numpy as np

from .geometry import MaskBox


def _sparkle_template(size: int) -> np.ndarray:
    """Create a soft four-point sparkle template similar to the visible mark."""
    canvas = np.zeros((size, size), dtype=np.float32)
    center = (size - 1) / 2
    half_width = size * 0.44
    half_height = size * 0.46
    points = np.array(
        [
            (center, center - half_height),
            (center + half_width * 0.16, center - half_height * 0.25),
            (center + half_width, center),
            (center + half_width * 0.16, center + half_height * 0.25),
            (center, center + half_height),
            (center - half_width * 0.16, center + half_height * 0.25),
            (center - half_width, center),
            (center - half_width * 0.16, center - half_height * 0.25),
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(canvas, [points], 1.0)
    return cv2.GaussianBlur(canvas, (5, 5), 0)


def _resolution_profile_fallback(width: int, height: int, fallback: MaskBox) -> MaskBox:
    """Use the distinct watermark placement of Gemini's 2752x1536 exports."""
    aspect_ratio = width / max(height, 1)
    if width < 2000 or abs(aspect_ratio - (16 / 9)) > 0.04:
        return fallback

    center_x = round(width * 0.913)
    center_y = round(height * 0.844)
    left = max(0, min(width - fallback.width, center_x - fallback.width // 2))
    top = max(0, min(height - fallback.height, center_y - fallback.height // 2))
    return MaskBox(left=left, top=top, right=left + fallback.width, bottom=top + fallback.height)


def detect_logo_box(rgb_array: np.ndarray, fallback: MaskBox) -> tuple[MaskBox, float]:
    """Refine the fixed Gemini position using a local sparkle-shape search.

    Detection is intentionally constrained around the calibrated location. A
    low-confidence result never moves the mask, preventing bright scene objects
    elsewhere in the image from being mistaken for the logo.
    """
    height, width = rgb_array.shape[:2]
    fallback = _resolution_profile_fallback(width, height, fallback)
    scale = max(0.5, min(width / 1376.0, height / 768.0))
    expected_x = (fallback.left + fallback.right) // 2
    expected_y = (fallback.top + fallback.bottom) // 2
    radius = max(round(70 * scale), round(max(fallback.width, fallback.height) * 0.75))

    search_left = max(0, expected_x - radius)
    search_top = max(0, expected_y - radius)
    search_right = min(width, expected_x + radius)
    search_bottom = min(height, expected_y + radius)
    gray = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2GRAY).astype(np.float32)
    search = gray[search_top:search_bottom, search_left:search_right]
    if min(search.shape) < 32:
        return fallback, 0.0

    high_pass = search - cv2.GaussianBlur(search, (0, 0), max(3.0, 10.0 * scale))
    best_score = float("-inf")
    best_raw_score = 0.0
    best_center: tuple[int, int] | None = None

    for base_size in (39, 45, 51, 57, 63):
        size = max(21, round(base_size * scale))
        if size >= search.shape[0] or size >= search.shape[1]:
            continue
        response = cv2.matchTemplate(high_pass, _sparkle_template(size), cv2.TM_CCOEFF_NORMED)
        _minimum, raw_score, _min_location, location = cv2.minMaxLoc(response)
        center_x = search_left + location[0] + size // 2
        center_y = search_top + location[1] + size // 2
        distance = float(np.hypot(center_x - expected_x, center_y - expected_y))
        adjusted_score = raw_score - distance * (0.006 / scale)
        if adjusted_score > best_score:
            best_score = adjusted_score
            best_raw_score = raw_score
            best_center = (center_x, center_y)

    # Only trust a visible shape. When the mark blends into a white background,
    # the enlarged calibrated mask remains safer than following a false match.
    if best_center is None or (best_score < 0.24 and best_raw_score < 0.45):
        return fallback, max(0.0, best_score)

    center_x, center_y = best_center
    left = max(0, min(width - fallback.width, center_x - fallback.width // 2))
    top = max(0, min(height - fallback.height, center_y - fallback.height // 2))
    refined = MaskBox(left=left, top=top, right=left + fallback.width, bottom=top + fallback.height)
    return refined, min(1.0, max(0.0, best_raw_score))
