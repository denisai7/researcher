from __future__ import annotations

from typing import Optional

from src.integrations.notebooklm.client import get_notebooklm_client
from src.models.material import MaterialType, ResearchMaterial
from src.models.result import ResearchResult
from src.utils.logging import logger


# Map user intent keywords to NotebookLM actions
INTENT_MAP = {
    "audio": "audio_overview",
    "podcast": "audio_overview",
    "listen": "audio_overview",
    "summary": "summary",
    "summarize": "summary",
    "summarise": "summary",
    "review": "summary",
    "overview": "summary",
    "study": "study_guide",
    "guide": "study_guide",
}

DEFAULT_ACTION = "summary"


def detect_intent(user_request: str) -> str:
    """Detect the desired output type from the user's natural language request."""
    request_lower = user_request.lower()
    for keyword, action in INTENT_MAP.items():
        if keyword in request_lower:
            return action
    return DEFAULT_ACTION


class NotebookLMAdapter:
    def __init__(self):
        self.client = get_notebooklm_client()

    @property
    def is_available(self) -> bool:
        return self.client.is_available

    async def create_project(self, name: str) -> Optional[str]:
        """Create a new NotebookLM notebook for a project."""
        return await self.client.create_notebook(name)

    async def upload_material(
        self, notebook_id: str, material: ResearchMaterial
    ) -> bool:
        """Upload a single material to NotebookLM."""
        if material.material_type in (MaterialType.LINK, MaterialType.YOUTUBE):
            return await self.client.add_source_url(notebook_id, material.source_value)
        elif material.material_type in (
            MaterialType.PDF,
            MaterialType.AUDIO,
            MaterialType.FILE,
        ):
            return await self.client.add_source_file(
                notebook_id, material.source_value
            )
        else:
            logger.warning(
                f"Unsupported material type for NotebookLM: {material.material_type}"
            )
            return False

    async def generate_result(
        self, notebook_id: str, action: str
    ) -> Optional[ResearchResult]:
        """Generate a result based on the detected action."""
        if action == "audio_overview":
            audio_ref = await self.client.generate_audio_overview(notebook_id)
            return ResearchResult(
                result_type="audio_overview",
                content=None,
                notebooklm_ref=audio_ref,
                file_path=audio_ref if audio_ref and not audio_ref.startswith("http") else None,
            )
        elif action in ("summary", "study_guide"):
            text = await self.client.get_summary(notebook_id)
            return ResearchResult(
                result_type=action,
                content=text,
                notebooklm_ref=notebook_id,
            )
        else:
            text = await self.client.get_summary(notebook_id)
            return ResearchResult(
                result_type="summary",
                content=text,
                notebooklm_ref=notebook_id,
            )

    async def delete_project(self, notebook_id: str) -> bool:
        """Delete a NotebookLM notebook."""
        return await self.client.delete_notebook(notebook_id)
