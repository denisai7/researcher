from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from src.models.material import MaterialType
from src.utils.logging import logger

YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"(?:https?://)?youtu\.be/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
]

EXTENSION_TYPE_MAP = {
    ".pdf": MaterialType.PDF,
    ".mp3": MaterialType.AUDIO,
    ".wav": MaterialType.AUDIO,
    ".ogg": MaterialType.AUDIO,
    ".m4a": MaterialType.AUDIO,
    ".flac": MaterialType.AUDIO,
    ".mp4": MaterialType.VIDEO,
    ".avi": MaterialType.VIDEO,
    ".mov": MaterialType.VIDEO,
    ".mkv": MaterialType.VIDEO,
    ".webm": MaterialType.VIDEO,
    ".jpg": MaterialType.IMAGE,
    ".jpeg": MaterialType.IMAGE,
    ".png": MaterialType.IMAGE,
    ".gif": MaterialType.IMAGE,
    ".webp": MaterialType.IMAGE,
    ".bmp": MaterialType.IMAGE,
}

SUPPORTED_NOTEBOOKLM_TYPES = {
    MaterialType.LINK,
    MaterialType.YOUTUBE,
    MaterialType.PDF,
    MaterialType.AUDIO,
    MaterialType.FILE,
}


def detect_material_type_from_extension(filename: str) -> MaterialType:
    from src.utils.files import get_file_extension

    ext = get_file_extension(filename)
    return EXTENSION_TYPE_MAP.get(ext, MaterialType.FILE)


def is_youtube_url(url: str) -> bool:
    return any(re.match(p, url) for p in YOUTUBE_PATTERNS)


def is_url(text: str) -> bool:
    try:
        result = urlparse(text.strip())
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def classify_text_content(text: str) -> Optional[MaterialType]:
    """Classify a text message as a URL/link type or None if it's a plain request."""
    text = text.strip()
    if is_youtube_url(text):
        return MaterialType.YOUTUBE
    if is_url(text):
        return MaterialType.LINK
    return None


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from a text message."""
    url_pattern = r"https?://[^\s<>\"')\]]+"
    return re.findall(url_pattern, text)


def is_format_supported(material_type: MaterialType) -> bool:
    return material_type in SUPPORTED_NOTEBOOKLM_TYPES


def suggest_conversion(material_type: MaterialType) -> Optional[str]:
    """Suggest a conversion strategy for unsupported types."""
    if material_type == MaterialType.IMAGE:
        return "Images are not directly supported. Consider using OCR or describing the image content."
    if material_type == MaterialType.VIDEO:
        return "Video files may need audio extraction before processing."
    return None
