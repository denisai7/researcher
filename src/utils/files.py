from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.utils.logging import logger

DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "researcher_downloads")

# Telegram Bot API file size limit (20 MB for download)
TELEGRAM_FILE_SIZE_LIMIT = 20 * 1024 * 1024
# NotebookLM source file size limit (200 MB)
NOTEBOOKLM_FILE_SIZE_LIMIT = 200 * 1024 * 1024


class FileSizeError(Exception):
    """Raised when a file exceeds size limits."""

    def __init__(self, file_name: str, file_size: int, limit: int, limit_source: str):
        self.file_name = file_name
        self.file_size = file_size
        self.limit = limit
        self.limit_source = limit_source
        size_mb = file_size / (1024 * 1024)
        limit_mb = limit / (1024 * 1024)
        super().__init__(
            f"File '{file_name}' is {size_mb:.1f} MB, "
            f"exceeding the {limit_source} limit of {limit_mb:.0f} MB."
        )


def ensure_download_dir() -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    return DOWNLOAD_DIR


def check_telegram_file_size(file_size: int | None, file_name: str) -> None:
    """Check if a Telegram file is within downloadable size limits.

    Raises FileSizeError if the file exceeds the Telegram Bot API limit.
    """
    if file_size is not None and file_size > TELEGRAM_FILE_SIZE_LIMIT:
        raise FileSizeError(
            file_name, file_size, TELEGRAM_FILE_SIZE_LIMIT, "Telegram Bot API"
        )


def check_notebooklm_file_size(file_path: str) -> None:
    """Check if a local file is within NotebookLM upload limits.

    Raises FileSizeError if the file exceeds the NotebookLM limit.
    """
    file_size = os.path.getsize(file_path)
    if file_size > NOTEBOOKLM_FILE_SIZE_LIMIT:
        raise FileSizeError(
            os.path.basename(file_path),
            file_size,
            NOTEBOOKLM_FILE_SIZE_LIMIT,
            "NotebookLM",
        )


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
