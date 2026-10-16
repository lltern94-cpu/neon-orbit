"""Загрузка настроек из переменных окружения."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

MAX_FILE_SIZE_MB = _int_env("MAX_FILE_SIZE_MB", 15)
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Ограничение размера результата, чтобы не исчерпать память.
MAX_OUTPUT_PIXELS = _int_env("MAX_OUTPUT_PIXELS", 16_000_000)
MAX_INPUT_SIDE = _int_env("MAX_INPUT_SIDE", 4096)

TEMP_DIR = Path(os.getenv("TEMP_DIR", str(BASE_DIR / "tmp")))
MODELS_DIR = Path(os.getenv("MODELS_DIR", str(BASE_DIR / "models")))
REALESRGAN_MODEL_PATH = os.getenv("REALESRGAN_MODEL_PATH", "").strip()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEFAULT_SCALE = _int_env("DEFAULT_SCALE", 2)
if DEFAULT_SCALE not in (2, 4):
    DEFAULT_SCALE = 2
