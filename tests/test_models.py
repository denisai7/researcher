from datetime import datetime, timezone

from src.models.material import MaterialStatus, MaterialType, ResearchMaterial
from src.models.project import ProjectStatus, ResearchProject
from src.models.result import ResearchResult


class TestResearchProject:
    def test_create_project(self):
        project = ResearchProject(
            user_id="123",
            project_name="Test Project",
            original_user_request="Make a summary",
        )
        assert project.user_id == "123"
        assert project.project_name == "Test Project"
        assert project.status == ProjectStatus.NEW
        assert project.project_id  # auto-generated

    def test_to_db_dict(self):
        project = ResearchProject(
            user_id="123",
            project_name="Test",
            original_user_request="Test request",
        )
        d = project.to_db_dict()
        assert d["user_id"] == "123"
        assert d["status"] == "new"
        assert "project_id" in d

    def test_from_db_row(self):
        row = {
            "project_id": "abc-123",
            "user_id": "456",
            "project_name": "From DB",
            "original_user_request": "Some request",
            "status": "completed",
            "notebooklm_project_id": "nlm-1",
            "result_type": "summary",
            "result_ref": "ref-1",
            "result_summary": "A summary",
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-01T01:00:00+00:00",
        }
        project = ResearchProject.from_db_row(row)
        assert project.project_id == "abc-123"
        assert project.status == ProjectStatus.COMPLETED
        assert project.notebooklm_project_id == "nlm-1"

    def test_status_enum_values(self):
        assert ProjectStatus.NEW.value == "new"
        assert ProjectStatus.MATERIALS_PREPARING.value == "materials_preparing"
        assert ProjectStatus.SENT_TO_NOTEBOOKLM.value == "sent_to_notebooklm"
        assert ProjectStatus.GENERATING.value == "generating"
        assert ProjectStatus.COMPLETED.value == "completed"
        assert ProjectStatus.ERROR.value == "error"
        assert ProjectStatus.CANCELLED.value == "cancelled"


class TestResearchMaterial:
    def test_create_material(self):
        material = ResearchMaterial(
            project_id="proj-1",
            material_type=MaterialType.PDF,
            source_value="/tmp/test.pdf",
            display_name="test.pdf",
        )
        assert material.material_type == MaterialType.PDF
        assert material.status == MaterialStatus.RECEIVED

    def test_to_db_dict(self):
        material = ResearchMaterial(
            project_id="proj-1",
            material_type=MaterialType.YOUTUBE,
            source_value="https://youtube.com/watch?v=abc",
            display_name="YouTube Video",
        )
        d = material.to_db_dict()
        assert d["material_type"] == "youtube"
        assert d["status"] == "received"

    def test_from_db_row(self):
        row = {
            "material_id": "mat-1",
            "project_id": "proj-1",
            "material_type": "audio",
            "source_value": "/tmp/audio.mp3",
            "display_name": "audio.mp3",
            "added_at": "2025-01-01T00:00:00+00:00",
            "status": "added_to_notebooklm",
        }
        material = ResearchMaterial.from_db_row(row)
        assert material.material_type == MaterialType.AUDIO
        assert material.status == MaterialStatus.ADDED_TO_NOTEBOOKLM


class TestResearchResult:
    def test_text_result(self):
        result = ResearchResult(
            result_type="summary",
            content="This is a summary",
        )
        assert result.is_text
        assert not result.is_file

    def test_file_result(self):
        result = ResearchResult(
            result_type="audio_overview",
            file_path="/tmp/audio.mp3",
            file_name="overview.mp3",
        )
        assert result.is_file
        assert not result.is_text
