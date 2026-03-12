from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MaterialType(str, Enum):
    LINK = "link"
    YOUTUBE = "youtube"
    PDF = "pdf"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"


class MaterialStatus(str, Enum):
    RECEIVED = "received"
    UPLOADING = "uploading"
    ADDED_TO_NOTEBOOKLM = "added_to_notebooklm"
    ERROR = "error"
    USED_IN_RESULT = "used_in_result"


class ResearchMaterial(BaseModel):
    material_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    material_type: MaterialType
    source_value: str
    display_name: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: MaterialStatus = MaterialStatus.RECEIVED

    def to_db_dict(self) -> dict:
        return {
            "material_id": self.material_id,
            "project_id": self.project_id,
            "material_type": self.material_type.value,
            "source_value": self.source_value,
            "display_name": self.display_name,
            "added_at": self.added_at.isoformat(),
            "status": self.status.value,
        }

    @classmethod
    def from_db_row(cls, row: dict) -> ResearchMaterial:
        return cls(
            material_id=row["material_id"],
            project_id=row["project_id"],
            material_type=MaterialType(row["material_type"]),
            source_value=row["source_value"],
            display_name=row["display_name"],
            added_at=datetime.fromisoformat(row["added_at"]),
            status=MaterialStatus(row["status"]),
        )
