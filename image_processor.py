"""Обработка изображений: Real-ESRGAN (если доступен) или OpenCV/Pillow.

Модуль никогда не утверждает, что использовался AI, если сработал запасной алгоритм.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from config import MAX_INPUT_SIDE, MAX_OUTPUT_PIXELS, MODELS_DIR, REALESRGAN_MODEL_PATH

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}

_realesrgan_unavailable_reason: Optional[str] = None
_realesrgan_checked = False


@dataclass
class EnhanceResult:
    output_path: Path
    scale: int
    used_ai: bool
    engine_name: str
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    had_transparency: bool


class ImageProcessingError(Exception):
    """Ошибка, которую можно показать пользователю (без внутренних деталей)."""


def is_supported_filename(name: str) -> bool:
    suffix = Path(name).suffix.lower()
    return suffix in SUPPORTED_FORMATS


def realesrgan_status() -> tuple[bool, str]:
    """Проверяет, доступен ли Real-ESRGAN в этой среде."""
    global _realesrgan_checked, _realesrgan_unavailable_reason
    if not _realesrgan_checked:
        _realesrgan_checked = True
        try:
            import torch  # noqa: F401
            from basicsr.archs.rrdbnet_arch import RRDBNet  # noqa: F401
            from realesrgan import RealESRGANer  # noqa: F401
        except Exception as exc:
            _realesrgan_unavailable_reason = (
                f"пакеты Real-ESRGAN/PyTorch не установлены ({type(exc).__name__})"
            )
            logger.info("Real-ESRGAN недоступен: %s", _realesrgan_unavailable_reason)
            return False, _realesrgan_unavailable_reason

        model_path = _resolve_model_path()
        if model_path is None:
            _realesrgan_unavailable_reason = (
                "файл модели Real-ESRGAN не найден (см. README, папка models/)"
            )
            logger.info("Real-ESRGAN недоступен: нет файла модели")
            return False, _realesrgan_unavailable_reason

        _realesrgan_unavailable_reason = None
        return True, str(model_path)

    if _realesrgan_unavailable_reason:
        return False, _realesrgan_unavailable_reason
    return True, "Real-ESRGAN готов"


def _resolve_model_path() -> Optional[Path]:
    candidates: list[Path] = []
    if REALESRGAN_MODEL_PATH:
        candidates.append(Path(REALESRGAN_MODEL_PATH))
    candidates.extend(
        [
            MODELS_DIR / "RealESRGAN_x4plus.pth",
            MODELS_DIR / "RealESRGAN_x2plus.pth",
            MODELS_DIR / "realesrgan-x4plus.pth",
        ]
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def enhance_image(input_path: Path, output_path: Path, scale: int) -> EnhanceResult:
    if scale not in (2, 4):
        raise ImageProcessingError("Неподдерживаемый масштаб.")

    try:
        image = Image.open(input_path)
        image = ImageOps.exif_transpose(image)
    except UnidentifiedImageError as exc:
        raise ImageProcessingError("Не удалось прочитать изображение.") from exc
    except OSError as exc:
        raise ImageProcessingError("Файл повреждён или недоступен.") from exc

    if image.format and image.format.upper() not in SUPPORTED_PIL_FORMATS:
        raise ImageProcessingError("Поддерживаются только JPG, PNG и WEBP.")

    original_size = image.size
    had_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )

    _guard_output_size(original_size[0], original_size[1], scale)

    rgba = image.convert("RGBA") if had_alpha else image.convert("RGB")
    rgba = _limit_input_size(rgba)

    rgb = rgba.convert("RGB")
    alpha = rgba.getchannel("A") if had_alpha else None

    used_ai = False
    engine_name = "opencv_pillow"
    upscaled_rgb: Optional[Image.Image] = None

    available, _reason = realesrgan_status()
    if available:
        try:
            upscaled_rgb = _enhance_with_realesrgan(rgb, scale)
            used_ai = True
            engine_name = "realesrgan"
            logger.info("Использован Real-ESRGAN, масштаб ×%s", scale)
        except Exception:
            logger.exception("Real-ESRGAN не смог обработать изображение, переход на запасной алгоритм")
            upscaled_rgb = None

    if upscaled_rgb is None:
        upscaled_rgb = _enhance_with_opencv_pillow(rgb, scale)
        used_ai = False
        engine_name = "opencv_pillow"
        logger.info("Использован запасной алгоритм OpenCV/Pillow, масштаб ×%s", scale)

    if alpha is not None:
        alpha_up = alpha.resize(upscaled_rgb.size, Image.Resampling.LANCZOS)
        result = upscaled_rgb.convert("RGBA")
        result.putalpha(alpha_up)
        output_path = output_path.with_suffix(".png")
        save_format = "PNG"
        save_kwargs: dict = {"optimize": True}
    else:
        result = upscaled_rgb.convert("RGB")
        output_path = output_path.with_suffix(".jpg")
        save_format = "JPEG"
        save_kwargs = {"quality": 92, "optimize": True, "subsampling": 1}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, format=save_format, **save_kwargs)

    return EnhanceResult(
        output_path=output_path,
        scale=scale,
        used_ai=used_ai,
        engine_name=engine_name,
        original_size=original_size,
        output_size=result.size,
        had_transparency=had_alpha,
    )


def _guard_output_size(width: int, height: int, scale: int) -> None:
    if width <= 0 or height <= 0:
        raise ImageProcessingError("Некорректный размер изображения.")
    out_pixels = width * height * scale * scale
    if out_pixels > MAX_OUTPUT_PIXELS:
        raise ImageProcessingError(
            "Изображение слишком большое для выбранного масштаба. "
            "Попробуйте масштаб ×2 или отправьте фото меньшего размера."
        )


def _limit_input_size(image: Image.Image) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= MAX_INPUT_SIDE:
        return image
    ratio = MAX_INPUT_SIDE / float(longest)
    new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
    logger.info("Вход уменьшен с %sx%s до %sx%s", width, height, new_size[0], new_size[1])
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _enhance_with_realesrgan(image: Image.Image, scale: int) -> Image.Image:
    import torch
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer

    model_path = _resolve_model_path()
    if model_path is None:
        raise RuntimeError("model missing")

    model_scale = 2 if "x2" in model_path.name.lower() else 4
    model = RRDBNet(
        num_in_ch=3,
        num_out_ch=3,
        num_feat=64,
        num_block=23,
        num_grow_ch=32,
        scale=model_scale,
    )
    half = torch.cuda.is_available()
    restorer = RealESRGANer(
        scale=model_scale,
        model_path=str(model_path),
        model=model,
        tile=256,
        tile_pad=10,
        pre_pad=0,
        half=half,
    )
    bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    output, _ = restorer.enhance(bgr, outscale=scale)
    rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _enhance_with_opencv_pillow(image: Image.Image, scale: int) -> Image.Image:
    """Мягкое улучшение без «перешарпа»: шум ↓, масштаб, локальный контраст, лёгкая резкость."""
    rgb = np.array(image)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    denoised = cv2.fastNlMeansDenoisingColored(
        bgr,
        None,
        h=3,
        hColor=3,
        templateWindowSize=7,
        searchWindowSize=21,
    )

    new_w = denoised.shape[1] * scale
    new_h = denoised.shape[0] * scale
    upscaled = cv2.resize(denoised, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    lab = cv2.cvtColor(upscaled, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.4, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    contrasted = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    blurred = cv2.GaussianBlur(contrasted, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(contrasted, 1.25, blurred, -0.25, 0)

    # Лёгкое сглаживание ореолов, чтобы результат выглядел естественнее.
    natural = cv2.bilateralFilter(sharpened, d=5, sigmaColor=20, sigmaSpace=20)
    out_rgb = cv2.cvtColor(natural, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(out_rgb)
    return pil_image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=40, threshold=4))


def safe_unlink(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        if path.exists():
            os.remove(path)
    except OSError:
        logger.warning("Не удалось удалить временный файл")
