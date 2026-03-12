from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResearchResult:
    """Result returned from NotebookLM processing."""
    result_type: str  # e.g. "summary", "audio_overview", "study_guide", etc.
    content: Optional[str] = None  # text content if applicable
    file_path: Optional[str] = None  # local file path if applicable
    file_name: Optional[str] = None  # original file name
    notebooklm_ref: Optional[str] = None  # reference ID in NotebookLM
    metadata: dict = field(default_factory=dict)

    @property
    def is_file(self) -> bool:
        return self.file_path is not None

    @property
    def is_text(self) -> bool:
        return self.content is not None and self.file_path is None
