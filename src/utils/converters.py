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
    MaterialType.IMAGE,
    MaterialType.VIDEO,
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


UNSUPPORTED_EXTENSION_HINTS: dict[str, str] = {
    ".doc": "Convert to PDF first (e.g., LibreOffice: soffice --convert-to pdf)",
    ".docx": "Convert to PDF first (e.g., LibreOffice: soffice --convert-to pdf)",
    ".ppt": "Convert to PDF first (e.g., LibreOffice: soffice --convert-to pdf)",
    ".pptx": "Convert to PDF first (e.g., LibreOffice: soffice --convert-to pdf)",
    ".xls": "Convert to PDF first (e.g., LibreOffice: soffice --convert-to pdf)",
    ".xlsx": "Convert to PDF first (e.g., LibreOffice: soffice --convert-to pdf)",
    ".txt": "Rename to .pdf or paste the text directly in the chat",
    ".rtf": "Convert to PDF first",
    ".epub": "Convert to PDF first (e.g., Calibre)",
    ".heic": "Convert to JPEG first",
    ".tiff": "Convert to PNG or JPEG first",
    ".tif": "Convert to PNG or JPEG first",
}


def suggest_conversion(material_type: MaterialType, filename: str = "") -> Optional[str]:
    """Suggest a conversion strategy for unsupported or problematic file types.

    Returns a hint string if the file should be converted before upload,
    or None if the format is natively supported.
    """
    # Check specific extension hints first -- some extensions map to FILE type
    # but aren't actually supported by NotebookLM natively
    if filename:
        from src.utils.files import get_file_extension

        ext = get_file_extension(filename)
        if ext in UNSUPPORTED_EXTENSION_HINTS:
            return UNSUPPORTED_EXTENSION_HINTS[ext]

    if material_type in SUPPORTED_NOTEBOOKLM_TYPES:
        return None

    return "This file format is not supported. Try converting to PDF, MP3, or a supported format."


# Extensions that can be auto-converted to PDF via LibreOffice
AUTO_CONVERT_TO_PDF = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".rtf", ".txt"}
# Extensions that can be auto-converted to JPEG via sips (macOS) or PIL
AUTO_CONVERT_TO_JPEG = {".heic", ".tiff", ".tif"}


def can_auto_convert(filename: str) -> bool:
    """Check if a file can be automatically converted to a supported format."""
    from src.utils.files import get_file_extension

    ext = get_file_extension(filename)
    return ext in AUTO_CONVERT_TO_PDF or ext in AUTO_CONVERT_TO_JPEG


def get_auto_convert_target(filename: str) -> Optional[str]:
    """Return the target format for auto-conversion, or None."""
    from src.utils.files import get_file_extension

    ext = get_file_extension(filename)
    if ext in AUTO_CONVERT_TO_PDF:
        return "pdf"
    if ext in AUTO_CONVERT_TO_JPEG:
        return "jpeg"
    return None


async def auto_convert_file(file_path: str) -> Optional[str]:
    """Attempt to auto-convert a file to a supported format.

    Returns the path to the converted file, or None if conversion failed.
    """
    import asyncio
    import os
    from src.utils.files import get_file_extension
    from src.utils.logging import logger

    ext = get_file_extension(file_path)
    base = os.path.splitext(file_path)[0]

    if ext in AUTO_CONVERT_TO_PDF:
        output_path = base + ".pdf"
        try:
            proc = await asyncio.create_subprocess_exec(
                "soffice", "--headless", "--convert-to", "pdf",
                "--outdir", os.path.dirname(file_path) or ".",
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=60)
            if proc.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Auto-converted {file_path} -> {output_path}")
                return output_path
        except (FileNotFoundError, asyncio.TimeoutError) as e:
            logger.warning(f"Auto-conversion failed for {file_path}: {e}")
        return None

    if ext in AUTO_CONVERT_TO_JPEG:
        output_path = base + ".jpeg"
        try:
            # Try macOS sips first
            proc = await asyncio.create_subprocess_exec(
                "sips", "-s", "format", "jpeg", file_path,
                "--out", output_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=30)
            if proc.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Auto-converted {file_path} -> {output_path}")
                return output_path
        except (FileNotFoundError, asyncio.TimeoutError) as e:
            logger.warning(f"Auto-conversion via sips failed for {file_path}: {e}")
        return None

    return None
