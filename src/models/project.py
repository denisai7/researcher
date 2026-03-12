from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    NEW = "new"
    MATERIALS_PREPARING = "materials_preparing"
    SENT_TO_NOTEBOOKLM = "sent_to_notebooklm"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class ResearchProject(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    project_name: str
    original_user_request: str
    status: ProjectStatus = ProjectStatus.NEW
    notebooklm_project_id: Optional[str] = None
    result_type: Optional[str] = None
    result_ref: Optional[str] = None
    result_summary: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_db_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "user_id": self.user_id,
            "project_name": self.project_name,
            "original_user_request": self.original_user_request,
            "status": self.status.value,
            "notebooklm_project_id": self.notebooklm_project_id,
            "result_type": self.result_type,
            "result_ref": self.result_ref,
            "result_summary": self.result_summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> ResearchProject:
        return cls(
            project_id=row["project_id"],
            user_id=row["user_id"],
            project_name=row["project_name"],
            original_user_request=row["original_user_request"],
            status=ProjectStatus(row["status"]),
            notebooklm_project_id=row.get("notebooklm_project_id"),
            result_type=row.get("result_type"),
            result_ref=row.get("result_ref"),
            result_summary=row.get("result_summary"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
