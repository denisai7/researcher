from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.utils.logging import logger


class NotebookLMClientWrapper:
    """Wrapper around notebooklm-py library.

    Uses the real NotebookLMClient async API from notebooklm-py>=0.1.1.
    Authentication is via stored browser tokens (see notebooklm-py docs).
    """

    def __init__(self):
        self._client = None

    async def _ensure_client(self):
        if self._client is not None:
            return
        try:
            from notebooklm import NotebookLMClient
            from notebooklm.auth import AuthTokens

            storage_path = os.environ.get("NOTEBOOKLM_STORAGE_PATH")
            if storage_path:
                auth = AuthTokens.from_storage(Path(storage_path))
            else:
                auth = AuthTokens.from_storage()

            self._client = NotebookLMClient(auth)
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
        # Synchronous check -- just verify the library can be imported.
        # Full auth check happens lazily in _ensure_client().
        try:
            import notebooklm  # noqa: F401
            return True
        except ImportError:
            return False

    async def create_notebook(self, title: str) -> Optional[str]:
        """Create a new notebook and return its ID."""
        await self._ensure_client()
        if not self._client:
            return None
        try:
            notebook = await self._client.notebooks.create(title=title)
            notebook_id = getattr(notebook, "id", str(notebook))
            logger.info(f"Created notebook: {notebook_id}")
            return notebook_id
        except Exception as e:
            logger.error(f"Failed to create notebook: {e}")
            raise

    async def add_source_url(self, notebook_id: str, url: str) -> bool:
        """Add a URL source to a notebook."""
        await self._ensure_client()
        if not self._client:
            return False
        try:
            await self._client.sources.add_url(notebook_id, url, wait=True)
            logger.info(f"Added URL source to notebook {notebook_id}: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to add URL source: {e}")
            raise

    async def add_source_file(self, notebook_id: str, file_path: str) -> bool:
        """Add a file source to a notebook."""
        await self._ensure_client()
        if not self._client:
            return False
        try:
            await self._client.sources.add_file(notebook_id, file_path, wait=True)
            logger.info(f"Added file source to notebook {notebook_id}: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to add file source: {e}")
            raise

    async def generate_audio_overview(self, notebook_id: str) -> Optional[str]:
        """Generate an audio overview and return the audio file path."""
        await self._ensure_client()
        if not self._client:
            return None
        try:
            status = await self._client.artifacts.generate_audio(notebook_id)
            # Wait for generation to complete
            await self._client.artifacts.wait_for_completion(
                notebook_id, status.artifact_id
            )
            # Download audio
            audio_path = await self._client.artifacts.download_audio(
                notebook_id, status.artifact_id
            )
            logger.info(f"Generated audio overview for notebook {notebook_id}")
            return str(audio_path)
        except Exception as e:
            logger.error(f"Failed to generate audio overview: {e}")
            raise

    async def get_summary(self, notebook_id: str) -> Optional[str]:
        """Get a summary/overview of the notebook contents."""
        await self._ensure_client()
        if not self._client:
            return None
        try:
            summary = await self._client.notebooks.get_summary(notebook_id)
            return str(summary) if summary else "No summary available."
        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            raise

    async def generate_study_guide(self, notebook_id: str) -> Optional[str]:
        """Generate a study guide for the notebook."""
        await self._ensure_client()
        if not self._client:
            return None
        try:
            status = await self._client.artifacts.generate_study_guide(notebook_id)
            await self._client.artifacts.wait_for_completion(
                notebook_id, status.artifact_id
            )
            # Get the artifact content
            artifact = await self._client.artifacts.get(
                notebook_id, status.artifact_id
            )
            return getattr(artifact, "content", str(artifact))
        except Exception as e:
            logger.error(f"Failed to generate study guide: {e}")
            raise

    async def delete_notebook(self, notebook_id: str) -> bool:
        """Delete a notebook."""
        await self._ensure_client()
        if not self._client:
            return False
        try:
            await self._client.notebooks.delete(notebook_id)
            logger.info(f"Deleted notebook: {notebook_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete notebook: {e}")
            raise


_instance: Optional[NotebookLMClientWrapper] = None


def get_notebooklm_client() -> NotebookLMClientWrapper:
    global _instance
    if _instance is None:
        _instance = NotebookLMClientWrapper()
    return _instance
