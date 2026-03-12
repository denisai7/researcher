from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.utils.logging import logger

DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "researcher_downloads")


def ensure_download_dir() -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    return DOWNLOAD_DIR


async def download_telegram_file(bot, file_id: str, file_name: str) -> str:
    """Download a file from Telegram and return the local path."""
    ensure_download_dir()
    local_path = os.path.join(DOWNLOAD_DIR, file_name)
    tg_file = await bot.get_file(file_id)
    await tg_file.download_to_drive(local_path)
    logger.info(f"Downloaded file to {local_path}")
    return local_path


def cleanup_file(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as e:
        logger.warning(f"Failed to clean up {path}: {e}")


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()
