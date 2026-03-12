from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.integrations.supabase.client import get_supabase_client
from src.models.material import ResearchMaterial
from src.models.project import ProjectStatus, ResearchProject


class ProjectRepository:
    TABLE = "research_projects"

    def __init__(self):
        self.client = get_supabase_client()

    def create(self, project: ResearchProject) -> ResearchProject:
        self.client.table(self.TABLE).insert(project.to_db_dict()).execute()
        return project

    def get_by_id(self, project_id: str) -> Optional[ResearchProject]:
        result = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("project_id", project_id)
            .execute()
        )
        if result.data:
            return ResearchProject.from_db_row(result.data[0])
        return None

    def update_status(self, project_id: str, status: ProjectStatus) -> None:
        self.client.table(self.TABLE).update(
            {"status": status.value, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("project_id", project_id).execute()

    def update(self, project_id: str, updates: dict) -> None:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.client.table(self.TABLE).update(updates).eq(
            "project_id", project_id
        ).execute()

    def get_recent_for_user(
        self, user_id: str, minutes: int = 2
    ) -> Optional[ResearchProject]:
        """Get the most recent project created within `minutes` for grouping."""
        result = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("status", ProjectStatus.NEW.value)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        project = ResearchProject.from_db_row(result.data[0])
        elapsed = (datetime.now(timezone.utc) - project.created_at).total_seconds()
        if elapsed <= minutes * 60:
            return project
        return None

    def get_active_context_project(
        self, user_id: str, hours: int = 24
    ) -> Optional[ResearchProject]:
        """Get the most recently updated project within `hours` for context memory."""
        result = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .neq("status", ProjectStatus.CANCELLED.value)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        project = ResearchProject.from_db_row(result.data[0])
        elapsed = (datetime.now(timezone.utc) - project.updated_at).total_seconds()
        if elapsed <= hours * 3600:
            return project
        return None

    def list_for_user(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> list[ResearchProject]:
        result = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return [ResearchProject.from_db_row(row) for row in result.data]

    def count_for_user(self, user_id: str) -> int:
        result = (
            self.client.table(self.TABLE)
            .select("project_id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        return result.count or 0

    def search(
        self,
        user_id: str,
        query: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[ResearchProject]:
        q = self.client.table(self.TABLE).select("*").eq("user_id", user_id)

        if query:
            q = q.or_(
                f"project_name.ilike.%{query}%,"
                f"original_user_request.ilike.%{query}%"
            )
        if status:
            q = q.eq("status", status)
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to)

        result = q.order("created_at", desc=True).limit(20).execute()
        return [ResearchProject.from_db_row(row) for row in result.data]

    def search_by_material(self, user_id: str, query: str) -> list[ResearchProject]:
        """Search projects by their material names/sources."""
        mat_result = (
            self.client.table(MaterialRepository.TABLE)
            .select("project_id")
            .or_(
                f"display_name.ilike.%{query}%,"
                f"source_value.ilike.%{query}%"
            )
            .execute()
        )
        project_ids = list({row["project_id"] for row in mat_result.data})
        if not project_ids:
            return []
        result = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .in_("project_id", project_ids)
            .order("created_at", desc=True)
            .execute()
        )
        return [ResearchProject.from_db_row(row) for row in result.data]

    def find_by_name(self, user_id: str, name: str) -> Optional[ResearchProject]:
        result = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .ilike("project_name", f"%{name}%")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return ResearchProject.from_db_row(result.data[0])
        return None

    def delete(self, project_id: str) -> None:
        self.client.table(MaterialRepository.TABLE).delete().eq(
            "project_id", project_id
        ).execute()
        self.client.table(self.TABLE).delete().eq(
            "project_id", project_id
        ).execute()


class MaterialRepository:
    TABLE = "research_materials"

    def __init__(self):
        self.client = get_supabase_client()

    def create(self, material: ResearchMaterial) -> ResearchMaterial:
        self.client.table(self.TABLE).insert(material.to_db_dict()).execute()
        return material

    def get_by_project(self, project_id: str) -> list[ResearchMaterial]:
        result = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("project_id", project_id)
            .order("added_at", desc=True)
            .execute()
        )
        return [ResearchMaterial.from_db_row(row) for row in result.data]

    def update_status(self, material_id: str, status: str) -> None:
        self.client.table(self.TABLE).update({"status": status}).eq(
            "material_id", material_id
        ).execute()

    def count_by_project(self, project_id: str) -> int:
        result = (
            self.client.table(self.TABLE)
            .select("material_id", count="exact")
            .eq("project_id", project_id)
            .execute()
        )
        return result.count or 0
