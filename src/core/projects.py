from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.integrations.supabase.repositories import (
    MaterialRepository,
    ProjectRepository,
)
from src.models.material import MaterialStatus, MaterialType, ResearchMaterial
from src.models.project import ProjectStatus, ResearchProject
from src.utils.logging import logger


def generate_project_name(user_request: str) -> str:
    """Auto-generate a short project name from the user request."""
    words = user_request.strip().split()
    # Take first 5 meaningful words
    name_words = [w for w in words if len(w) > 2][:5]
    if not name_words:
        name_words = words[:3]
    name = " ".join(name_words)
    if len(name) > 60:
        name = name[:57] + "..."
    return name or "Untitled Research"


class ProjectManager:
    def __init__(
        self,
        project_repo: Optional[ProjectRepository] = None,
        material_repo: Optional[MaterialRepository] = None,
    ):
        self.project_repo = project_repo or ProjectRepository()
        self.material_repo = material_repo or MaterialRepository()

    def create_project(self, user_id: str, request_text: str) -> ResearchProject:
        project = ResearchProject(
            user_id=user_id,
            project_name=generate_project_name(request_text),
            original_user_request=request_text,
            status=ProjectStatus.NEW,
        )
        self.project_repo.create(project)
        logger.info(f"Created project {project.project_id}: {project.project_name}")
        return project

    def add_material(
        self,
        project_id: str,
        material_type: MaterialType,
        source_value: str,
        display_name: str,
    ) -> ResearchMaterial:
        material = ResearchMaterial(
            project_id=project_id,
            material_type=material_type,
            source_value=source_value,
            display_name=display_name,
        )
        self.material_repo.create(material)
        logger.info(
            f"Added material {material.material_id} ({material_type}) to project {project_id}"
        )
        return material

    def update_status(self, project_id: str, status: ProjectStatus) -> None:
        self.project_repo.update_status(project_id, status)
        logger.info(f"Project {project_id} status -> {status.value}")

    def update_result(
        self,
        project_id: str,
        result_type: str,
        result_ref: Optional[str] = None,
        result_summary: Optional[str] = None,
    ) -> None:
        updates = {
            "result_type": result_type,
            "status": ProjectStatus.COMPLETED.value,
        }
        if result_ref:
            updates["result_ref"] = result_ref
        if result_summary:
            updates["result_summary"] = result_summary[:1000]
        self.project_repo.update(project_id, updates)

    def rename_project(self, project_id: str, new_name: str) -> None:
        self.project_repo.update(project_id, {"project_name": new_name})
        logger.info(f"Renamed project {project_id} to '{new_name}'")

    def cancel_project(self, project_id: str) -> None:
        self.update_status(project_id, ProjectStatus.CANCELLED)

    def get_project(self, project_id: str) -> Optional[ResearchProject]:
        return self.project_repo.get_by_id(project_id)

    def get_materials(self, project_id: str) -> list[ResearchMaterial]:
        return self.material_repo.get_by_project(project_id)

    def list_projects(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> list[ResearchProject]:
        return self.project_repo.list_for_user(user_id, limit, offset)

    def count_projects(self, user_id: str) -> int:
        return self.project_repo.count_for_user(user_id)

    def count_materials(self, project_id: str) -> int:
        return self.material_repo.count_by_project(project_id)

    def search_projects(
        self,
        user_id: str,
        query: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[ResearchProject]:
        # Try full-text search first, fall back to ilike
        results = []
        if query:
            try:
                results = self.project_repo.fulltext_search(
                    user_id, query, status, date_from, date_to
                )
            except Exception:
                logger.debug("Full-text search failed, falling back to ilike")
                results = []

        if not results:
            results = self.project_repo.search(
                user_id, query, status, date_from, date_to
            )

        # Also search material names/sources
        if query:
            material_results = self.project_repo.search_by_material(user_id, query)
            seen = {p.project_id for p in results}
            for p in material_results:
                if p.project_id not in seen:
                    results.append(p)
        return results

    def find_project_by_name(
        self, user_id: str, name: str
    ) -> Optional[ResearchProject]:
        return self.project_repo.find_by_name(user_id, name)

    def delete_project(self, project_id: str) -> None:
        self.project_repo.delete(project_id)
        logger.info(f"Deleted project {project_id}")

    def get_context_project(
        self, user_id: str, hours: int = 24
    ) -> Optional[ResearchProject]:
        """Get the active context project for follow-up requests."""
        return self.project_repo.get_active_context_project(user_id, hours)

    def update_material_status(
        self, material_id: str, status: MaterialStatus
    ) -> None:
        self.material_repo.update_status(material_id, status.value)
