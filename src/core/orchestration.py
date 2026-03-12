from __future__ import annotations

import asyncio
from typing import Optional

from src.core.grouping import MessageGrouper
from src.core.projects import ProjectManager
from src.models.material import MaterialType, ResearchMaterial
from src.models.project import ProjectStatus, ResearchProject
from src.models.result import ResearchResult
from src.utils.converters import classify_text_content, extract_urls
from src.utils.logging import logger
from src.workers.tasks import ResearchTaskProcessor


class ResearchOrchestrator:
    """Top-level orchestrator that coordinates the full research workflow."""

    def __init__(
        self,
        project_manager: Optional[ProjectManager] = None,
        grouper: Optional[MessageGrouper] = None,
        processor: Optional[ResearchTaskProcessor] = None,
    ):
        self.project_manager = project_manager or ProjectManager()
        self.grouper = grouper or MessageGrouper(self.project_manager.project_repo)
        self.processor = processor or ResearchTaskProcessor(self.project_manager)

    def handle_new_message(
        self,
        user_id: str,
        text: str,
        materials: Optional[list[dict]] = None,
    ) -> tuple[ResearchProject, bool]:
        """Handle an incoming message. Returns (project, is_new).

        materials: list of dicts with keys:
            - type: MaterialType
            - source: str (file path, URL, or file_id)
            - name: str (display name)
        """
        # Check grouping window
        should_group, existing = self.grouper.should_group(user_id)

        if should_group and existing:
            project = existing
            is_new = False
            # Append text to request if it's meaningful
            if text and not classify_text_content(text):
                self.project_manager.project_repo.update(
                    project.project_id,
                    {
                        "original_user_request": (
                            project.original_user_request + "\n" + text
                        )
                    },
                )
        else:
            request_text = text or "Research request"
            project = self.project_manager.create_project(user_id, request_text)
            is_new = True

        # Add URLs found in the text
        if text:
            urls = extract_urls(text)
            for url in urls:
                url_type = classify_text_content(url)
                if url_type:
                    self.project_manager.add_material(
                        project.project_id, url_type, url, url
                    )

        # Add explicit materials
        if materials:
            for mat in materials:
                self.project_manager.add_material(
                    project.project_id,
                    mat["type"],
                    mat["source"],
                    mat["name"],
                )

        return project, is_new

    async def process_project(
        self,
        project: ResearchProject,
        status_callback=None,
    ) -> Optional[ResearchResult]:
        """Kick off async processing of a project."""
        return await self.processor.process_project(project, status_callback)

    def add_material_to_project(
        self,
        project_id: str,
        material_type: MaterialType,
        source_value: str,
        display_name: str,
    ) -> ResearchMaterial:
        return self.project_manager.add_material(
            project_id, material_type, source_value, display_name
        )
