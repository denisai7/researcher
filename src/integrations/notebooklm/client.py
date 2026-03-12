from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from src.utils.logging import logger


class NotebookLMClientWrapper:
    """Wrapper around notebooklm-py library.

    Uses the real NotebookLMClient async API from notebooklm-py.
    Authentication is via stored browser tokens (see notebooklm-py docs).
    """

    def __init__(self):
        self._client = None

    async def _ensure_client(self):
        if self._client is not None:
            return
        try:
            from notebooklm import NotebookLMClient

            storage_path = os.environ.get("NOTEBOOKLM_STORAGE_PATH")
            if storage_path:
                self._client = await NotebookLMClient.from_storage(
                    storage_path=Path(storage_path)
                )
            else:
                self._client = await NotebookLMClient.from_storage()

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
        """Synchronous check -- just verify the library can be imported."""
        try:
            import notebooklm  # noqa: F401
            return True
        except ImportError:
            return False

    async def close(self):
        """Close the underlying client session."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    async def create_notebook(self, title: str) -> Optional[str]:
        """Create a new notebook and return its ID."""
        await self._ensure_client()
        if not self._client:
            return None
        try:
            notebook = await self._client.notebooks.create(title=title)
            notebook_id = notebook.id
            logger.info(f"Created notebook: {notebook_id}")
            return notebook_id
        except Exception as e:
            logger.error(f"Failed to create notebook: {e}")
            raise

    async def add_source_url(self, notebook_id: str, url: str) -> bool:
        """Add a URL source (web page or YouTube) to a notebook."""
        await self._ensure_client()
        if not self._client:
            return False
        try:
            await self._client.sources.add_url(
                notebook_id, url, wait=True, wait_timeout=120.0
            )
            logger.info(f"Added URL source to notebook {notebook_id}: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to add URL source: {e}")
            raise

    async def add_source_file(self, notebook_id: str, file_path: str) -> bool:
        """Add a file source to a notebook (PDF, audio, video, image, etc.)."""
        await self._ensure_client()
        if not self._client:
            return False
        try:
            await self._client.sources.add_file(
                notebook_id, file_path, wait=True, wait_timeout=120.0
            )
            logger.info(f"Added file source to notebook {notebook_id}: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to add file source: {e}")
            raise

    async def generate_audio_overview(
        self, notebook_id: str, instructions: Optional[str] = None
    ) -> Optional[str]:
        """Generate an audio overview and return the local audio file path."""
        await self._ensure_client()
        if not self._client:
            return None
        try:
            status = await self._client.artifacts.generate_audio(
                notebook_id, instructions=instructions
            )
            await self._client.artifacts.wait_for_completion(
                notebook_id, status.task_id
            )
            # Download to a temp file
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"notebooklm_audio_{notebook_id}.mp3",
            )
            await self._client.artifacts.download_audio(notebook_id, output_path)
            logger.info(f"Generated audio overview for notebook {notebook_id}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to generate audio overview: {e}")
            raise

    async def generate_summary(self, notebook_id: str) -> Optional[str]:
        """Generate a briefing doc / summary report and return its text content."""
        await self._ensure_client()
        if not self._client:
            return None
        try:
            from notebooklm import ReportFormat

            status = await self._client.artifacts.generate_report(
                notebook_id, report_format=ReportFormat.BRIEFING_DOC
            )
            await self._client.artifacts.wait_for_completion(
                notebook_id, status.task_id
            )
            # Download as markdown text
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"notebooklm_summary_{notebook_id}.md",
            )
            await self._client.artifacts.download_report(notebook_id, output_path)
            content = Path(output_path).read_text(encoding="utf-8")
            # Clean up temp file
            try:
                os.unlink(output_path)
            except OSError:
                pass
            return content if content else "No summary available."
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            raise

    async def generate_study_guide(self, notebook_id: str) -> Optional[str]:
        """Generate a study guide and return its text content."""
        await self._ensure_client()
        if not self._client:
            return None
        try:
            status = await self._client.artifacts.generate_study_guide(notebook_id)
            await self._client.artifacts.wait_for_completion(
                notebook_id, status.task_id
            )
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"notebooklm_guide_{notebook_id}.md",
            )
            await self._client.artifacts.download_report(notebook_id, output_path)
            content = Path(output_path).read_text(encoding="utf-8")
            try:
                os.unlink(output_path)
            except OSError:
                pass
            return content if content else "No study guide available."
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
