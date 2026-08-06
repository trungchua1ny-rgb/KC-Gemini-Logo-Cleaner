from __future__ import annotations

from dataclasses import dataclass

from .models import MaskConfig


@dataclass(frozen=True)
class MaskBox:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def calculate_mask_box(image_width: int, image_height: int, config: MaskConfig) -> MaskBox:
    """Calculate a resolution-independent bottom-right logo region."""
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Kích thước ảnh phải lớn hơn 0.")
    config.validate()

    logo_width = max(4, round(image_width * config.width_percent / 100))
    logo_height = max(4, round(image_height * config.height_percent / 100))
    margin_right = round(image_width * config.right_margin_percent / 100)
    margin_bottom = round(image_height * config.bottom_margin_percent / 100)
    padding = round(min(image_width, image_height) * config.padding_percent / 100)

    right = min(image_width, image_width - margin_right + padding)
    bottom = min(image_height, image_height - margin_bottom + padding)
    left = max(0, right - logo_width - padding * 2)
    top = max(0, bottom - logo_height - padding * 2)

    if left >= right or top >= bottom:
        raise ValueError("Vùng logo không hợp lệ với kích thước ảnh hiện tại.")

    return MaskBox(left=left, top=top, right=right, bottom=bottom)

