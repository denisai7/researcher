from __future__ import annotations

import os
from typing import Optional

from src.utils.logging import logger


class NotebookLMClient:
    """Wrapper around notebooklm-py library.

    This client abstracts the notebooklm-py library interactions.
    The actual library API may vary -- this provides the interface
    the rest of the codebase expects.
    """

    def __init__(self):
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        try:
            from notebooklm import NotebookLM

            cookies_path = os.environ.get("GOOGLE_COOKIES_PATH", "./cookies.json")
            self._client = NotebookLM(cookies_path=cookies_path)
            logger.info("NotebookLM client initialized")
        except ImportError:
            logger.warning(
                "notebooklm-py not installed. NotebookLM features unavailable."
            )
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize NotebookLM client: {e}")
            self._client = None

    @property
    def is_available(self) -> bool:
        self._ensure_client()
        return self._client is not None

    async def create_notebook(self, title: str) -> Optional[str]:
        """Create a new notebook and return its ID."""
        self._ensure_client()
        if not self._client:
            return None
        try:
            notebook = self._client.create_notebook(title=title)
            notebook_id = getattr(notebook, "id", str(notebook))
            logger.info(f"Created notebook: {notebook_id}")
            return notebook_id
        except Exception as e:
            logger.error(f"Failed to create notebook: {e}")
            raise

    async def add_source_url(self, notebook_id: str, url: str) -> bool:
        """Add a URL source to a notebook."""
        self._ensure_client()
        if not self._client:
            return False
        try:
            notebook = self._client.get_notebook(notebook_id)
            notebook.add_source(url=url)
            logger.info(f"Added URL source to notebook {notebook_id}: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to add URL source: {e}")
            raise

    async def add_source_file(self, notebook_id: str, file_path: str) -> bool:
        """Add a file source to a notebook."""
        self._ensure_client()
        if not self._client:
            return False
        try:
            notebook = self._client.get_notebook(notebook_id)
            notebook.add_source(file_path=file_path)
            logger.info(f"Added file source to notebook {notebook_id}: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to add file source: {e}")
            raise

    async def generate_audio_overview(self, notebook_id: str) -> Optional[str]:
        """Generate an audio overview and return the audio URL/path."""
        self._ensure_client()
        if not self._client:
            return None
        try:
            notebook = self._client.get_notebook(notebook_id)
            audio = notebook.get_audio_overview()
            logger.info(f"Generated audio overview for notebook {notebook_id}")
            return getattr(audio, "url", str(audio))
        except Exception as e:
            logger.error(f"Failed to generate audio overview: {e}")
            raise

    async def get_summary(self, notebook_id: str) -> Optional[str]:
        """Get a summary/overview of the notebook contents."""
        self._ensure_client()
        if not self._client:
            return None
        try:
            notebook = self._client.get_notebook(notebook_id)
            # Try to get study guide or summary
            if hasattr(notebook, "get_study_guide"):
                return str(notebook.get_study_guide())
            if hasattr(notebook, "get_summary"):
                return str(notebook.get_summary())
            # Fallback: get notebook notes
            notes = notebook.get_notes() if hasattr(notebook, "get_notes") else []
            return "\n".join(str(n) for n in notes) if notes else "No summary available."
        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            raise

    async def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook."""
        self._ensure_client()
        if not self._client:
            return False
        try:
            self._client.delete_notebook(notebook_id)
            logger.info(f"Deleted notebook: {notebook_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete notebook: {e}")
            raise


_instance: Optional[NotebookLMClient] = None


def get_notebooklm_client() -> NotebookLMClient:
    global _instance
    if _instance is None:
        _instance = NotebookLMClient()
    return _instance
