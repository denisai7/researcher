from __future__ import annotations

from typing import Optional

from src.integrations.supabase.repositories import ProjectRepository
from src.models.project import ResearchProject
from src.utils.logging import logger

GROUPING_WINDOW_MINUTES = 2


class MessageGrouper:
    """Groups incoming messages into projects using a 2-minute window."""

    def __init__(self, project_repo: Optional[ProjectRepository] = None):
        self.project_repo = project_repo or ProjectRepository()

    def find_active_project(self, user_id: str) -> Optional[ResearchProject]:
        """Find a project within the grouping window to attach new messages to."""
        project = self.project_repo.get_recent_for_user(
            user_id, minutes=GROUPING_WINDOW_MINUTES
        )
        if project:
            logger.info(
                f"Grouping message into existing project {project.project_id} "
                f"({project.project_name})"
            )
        return project

    def should_group(self, user_id: str) -> tuple[bool, Optional[ResearchProject]]:
        """Check if the next message should be grouped into an existing project.

        Returns (should_group, existing_project).
        """
        project = self.find_active_project(user_id)
        return (project is not None, project)
