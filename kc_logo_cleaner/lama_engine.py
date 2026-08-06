from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from .geometry import MaskBox


MODEL_FILENAME = "inpainting_lama_2025jan.onnx"
MODEL_URL = (
    "https://huggingface.co/opencv/inpainting_lama/resolve/main/"
    "inpainting_lama_2025jan.onnx?download=true"
)
MODEL_SHA256 = "7df918ac3921d3daf0aae1d219776cf0dc4e4935f035af81841b40adcf74fdf2"


class LamaModelError(RuntimeError):
    """Raised when the optional AI inpainting model cannot be used."""


def model_directory() -> Path:
    override = os.environ.get("KC_LOGO_CLEANER_MODEL_DIR")
    if override:
        return Path(override).expanduser()

    bundled = Path(__file__).resolve().parent.parent / "models"
    if bundled.exists() and os.access(bundled, os.W_OK):
        return bundled

    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / "KC Gemini Logo Cleaner" / "models"


def model_path() -> Path:
    return model_directory() / MODEL_FILENAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_is_ready(path: Path | None = None) -> bool:
    candidate = path or model_path()
    return candidate.is_file() and candidate.stat().st_size > 90_000_000


def ensure_model(download: bool = True) -> Path:
    destination = model_path()
    if model_is_ready(destination):
        return destination
    if not download:
        raise LamaModelError("Chưa có model AI LaMa. Hãy tải model trước khi xử lý.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix="lama-model-", suffix=".download", dir=destination.parent
    )
    os.close(temporary_fd)
    temporary = Path(temporary_name)
    try:
        request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "KC-Gemini-Logo-Cleaner/1.2"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if _sha256(temporary) != MODEL_SHA256:
            raise LamaModelError("Model AI tải về không hợp lệ (sai mã kiểm tra SHA-256).")
        os.replace(temporary, destination)
        return destination
    except Exception as error:
        raise LamaModelError(f"Không thể tải model AI LaMa: {error}") from error
    finally:
        temporary.unlink(missing_ok=True)


@lru_cache(maxsize=1)
def _session(path_text: str) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.log_severity_level = 3
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    try:
        return ort.InferenceSession(
            path_text,
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
    except Exception as error:
        raise LamaModelError(f"Không thể khởi tạo model AI LaMa: {error}") from error


def _context_crop(width: int, height: int, box: MaskBox) -> tuple[int, int, int, int]:
    # Keep roughly the same scene context at every output resolution. The crop
    # is moved inside image bounds instead of padded, so the model never sees a
    # synthetic black border next to the bottom-right logo.
    scale = max(width / 1376.0, height / 768.0)
    side = round(512 * scale)
    side = max(side, max(box.width, box.height) * 7)
    side = min(side, width, height)

    center_x = (box.left + box.right) // 2
    center_y = (box.top + box.bottom) // 2
    left = max(0, min(width - side, center_x - side // 2))
    top = max(0, min(height - side, center_y - side // 2))
    return left, top, left + side, top + side


def _soft_composite(
    original: np.ndarray,
    generated: np.ndarray,
    mask: np.ndarray,
    feather_radius: int,
) -> np.ndarray:
    if feather_radius <= 0:
        alpha = (mask > 0).astype(np.float32)
    else:
        radius = max(1, feather_radius)
        kernel = radius * 2 + 1
        alpha = cv2.GaussianBlur(mask, (kernel, kernel), 0).astype(np.float32) / 255.0
    alpha = alpha[:, :, np.newaxis]
    return np.clip(generated * alpha + original * (1.0 - alpha), 0, 255).astype(np.uint8)


def lama_inpaint(
    rgb_array: np.ndarray,
    full_mask: np.ndarray,
    box: MaskBox,
    feather_radius: int = 3,
    download_model: bool = True,
) -> np.ndarray:
    """Reconstruct the logo area with LaMa while preserving all other pixels."""
    height, width = rgb_array.shape[:2]
    left, top, right, bottom = _context_crop(width, height, box)
    crop = rgb_array[top:bottom, left:right]
    crop_mask = full_mask[top:bottom, left:right]
    crop_height, crop_width = crop.shape[:2]

    resized = cv2.resize(crop, (512, 512), interpolation=cv2.INTER_AREA)
    resized_mask = cv2.resize(crop_mask, (512, 512), interpolation=cv2.INTER_NEAREST)
    resized_mask = (resized_mask > 0).astype(np.float32)

    # The OpenCV-published model was exported using BGR channel order.
    bgr = cv2.cvtColor(resized, cv2.COLOR_RGB2BGR).astype(np.float32) / 255.0
    image_input = np.transpose(bgr, (2, 0, 1))[np.newaxis, ...]
    mask_input = resized_mask[np.newaxis, np.newaxis, ...]

    path = ensure_model(download_model)
    try:
        prediction = _session(str(path)).run(
            ["output"], {"image": image_input, "mask": mask_input}
        )[0][0]
    except Exception as error:
        raise LamaModelError(f"AI không thể phục hồi vùng logo: {error}") from error

    predicted_bgr = np.transpose(prediction, (1, 2, 0))
    # Some exports return 0..255 while others return 0..1. Handle both safely.
    if float(np.nanmax(predicted_bgr)) <= 2.0:
        predicted_bgr *= 255.0
    predicted_rgb = cv2.cvtColor(
        np.clip(predicted_bgr, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB
    )
    generated = cv2.resize(predicted_rgb, (crop_width, crop_height), interpolation=cv2.INTER_LANCZOS4)

    repaired_crop = _soft_composite(crop, generated, crop_mask, feather_radius)
    result = rgb_array.copy()
    result[top:bottom, left:right] = repaired_crop
    return result

