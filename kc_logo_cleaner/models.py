from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


InpaintMethod = Literal["texture-patch", "telea", "navier-stokes"]
MaskShape = Literal["gemini-sparkle", "rounded-rectangle", "ellipse"]


@dataclass(frozen=True)
class MaskConfig:
    # Calibrated from real 1376×768 Gemini/Google Flow image outputs.
    # The values remain proportional for other output resolutions.
    width_percent: float = 4.0
    height_percent: float = 7.5
    right_margin_percent: float = 5.0
    bottom_margin_percent: float = 9.3
    padding_percent: float = 0.4
    inpaint_radius: float = 4.0
    feather_radius: int = 3
    method: InpaintMethod = "texture-patch"
    shape: MaskShape = "rounded-rectangle"

    def validate(self) -> None:
        for label, value in (
            ("Chiều rộng logo", self.width_percent),
            ("Chiều cao logo", self.height_percent),
        ):
            if not 0.5 <= value <= 25:
                raise ValueError(f"{label} phải nằm trong khoảng 0.5%–25%.")

        for label, value in (
            ("Lề phải", self.right_margin_percent),
            ("Lề dưới", self.bottom_margin_percent),
            ("Padding", self.padding_percent),
        ):
            if not 0 <= value <= 20:
                raise ValueError(f"{label} phải nằm trong khoảng 0%–20%.")

        if not 1 <= self.inpaint_radius <= 30:
            raise ValueError("Bán kính phục hồi phải nằm trong khoảng 1–30 px.")
        if not 0 <= self.feather_radius <= 31:
            raise ValueError("Độ mềm viền phải nằm trong khoảng 0–31 px.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProcessingResult:
    source: Path
    output: Path | None
    status: Literal["completed", "failed", "cancelled"]
    width: int | None = None
    height: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": str(self.source),
            "output": str(self.output) if self.output else None,
            "status": self.status,
            "width": self.width,
            "height": self.height,
            "error": self.error,
        }
