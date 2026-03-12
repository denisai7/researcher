"""Tests for the ResearchOrchestrator -- Phase 1 core flow."""

from unittest.mock import MagicMock, patch

from src.core.orchestration import ResearchOrchestrator
from src.models.material import MaterialType
from src.models.project import ProjectStatus, ResearchProject


def _make_orchestrator(recent_project=None):
    """Create an orchestrator with mocked repos."""
    project_repo = MagicMock()
    material_repo = MagicMock()

    # Mock get_recent_for_user for grouping
    project_repo.get_recent_for_user.return_value = recent_project

    # Mock create to return the project as-is
    project_repo.create.side_effect = lambda p: p

    # Mock material create
    material_repo.create.side_effect = lambda m: m

    from src.core.projects import ProjectManager
    from src.core.grouping import MessageGrouper

    pm = ProjectManager(project_repo=project_repo, material_repo=material_repo)
    grouper = MessageGrouper(project_repo=project_repo)
    processor = MagicMock()

    orch = ResearchOrchestrator(
        project_manager=pm, grouper=grouper, processor=processor
    )
    return orch, project_repo, material_repo


class TestNewProjectCreation:
    def test_creates_project_from_text(self):
        orch, proj_repo, mat_repo = _make_orchestrator()

        project, is_new = orch.handle_new_message("user1", "summarize this paper")
        assert is_new is True
        assert project.user_id == "user1"
        assert project.status == ProjectStatus.NEW
        assert project.original_user_request == "summarize this paper"
        proj_repo.create.assert_called_once()

    def test_creates_project_with_auto_name(self):
        orch, _, _ = _make_orchestrator()

        project, _ = orch.handle_new_message("user1", "make audio review of AI trends")
        assert project.project_name  # auto-generated, not empty
        assert len(project.project_name) <= 60

    def test_creates_project_with_empty_text(self):
        orch, proj_repo, _ = _make_orchestrator()

        project, is_new = orch.handle_new_message("user1", "")
        assert is_new is True
        assert project.original_user_request == "Research request"

    def test_creates_project_with_materials(self):
        orch, _, mat_repo = _make_orchestrator()

        materials = [
            {"type": MaterialType.PDF, "source": "/tmp/paper.pdf", "name": "paper.pdf"},
            {"type": MaterialType.AUDIO, "source": "/tmp/voice.ogg", "name": "voice.ogg"},
        ]
        project, is_new = orch.handle_new_message("user1", "review this", materials)
        assert is_new is True
        assert mat_repo.create.call_count == 2

    def test_extracts_urls_from_text(self):
        orch, _, mat_repo = _make_orchestrator()

        project, _ = orch.handle_new_message(
            "user1", "check https://example.com/article"
        )
        # URL should be added as a material
        assert mat_repo.create.call_count == 1
        created_mat = mat_repo.create.call_args[0][0]
        assert created_mat.material_type == MaterialType.LINK
        assert created_mat.source_value == "https://example.com/article"

    def test_extracts_youtube_url(self):
        orch, _, mat_repo = _make_orchestrator()

        project, _ = orch.handle_new_message(
            "user1", "summarize https://www.youtube.com/watch?v=abc123"
        )
        created_mat = mat_repo.create.call_args[0][0]
        assert created_mat.material_type == MaterialType.YOUTUBE

    def test_text_and_file_together(self):
        orch, _, mat_repo = _make_orchestrator()

        materials = [
            {"type": MaterialType.PDF, "source": "/tmp/doc.pdf", "name": "doc.pdf"},
        ]
        project, _ = orch.handle_new_message(
            "user1",
            "review this https://example.com",
            materials,
        )
        # 1 URL from text + 1 explicit file
        assert mat_repo.create.call_count == 2


class TestMessageGrouping:
    def test_groups_into_existing_project(self):
        existing = ResearchProject(
            user_id="user1",
            project_name="Active Project",
            original_user_request="initial request",
            status=ProjectStatus.NEW,
        )
        orch, proj_repo, mat_repo = _make_orchestrator(recent_project=existing)

        materials = [
            {"type": MaterialType.IMAGE, "source": "/tmp/photo.jpg", "name": "photo.jpg"},
        ]
        project, is_new = orch.handle_new_message("user1", "", materials)

        assert is_new is False
        assert project.project_id == existing.project_id
        # Should NOT create a new project
        proj_repo.create.assert_not_called()
        # Should add material to existing project
        assert mat_repo.create.call_count == 1
        created_mat = mat_repo.create.call_args[0][0]
        assert created_mat.project_id == existing.project_id

    def test_appends_text_to_grouped_project(self):
        existing = ResearchProject(
            user_id="user1",
            project_name="Active",
            original_user_request="first message",
            status=ProjectStatus.NEW,
        )
        orch, proj_repo, _ = _make_orchestrator(recent_project=existing)

        project, is_new = orch.handle_new_message("user1", "also check this")
        assert is_new is False
        # Should update the project with appended text
        proj_repo.update.assert_called_once()
        update_args = proj_repo.update.call_args[0]
        assert existing.project_id == update_args[0]
        assert "also check this" in update_args[1]["original_user_request"]

    def test_no_grouping_creates_new_project(self):
        orch, proj_repo, _ = _make_orchestrator(recent_project=None)

        project, is_new = orch.handle_new_message("user1", "brand new request")
        assert is_new is True
        proj_repo.create.assert_called_once()


class TestStatusConfirmation:
    def test_new_project_has_new_status(self):
        orch, _, _ = _make_orchestrator()

        project, is_new = orch.handle_new_message("user1", "test request")
        assert project.status == ProjectStatus.NEW

    def test_status_message_for_new(self):
        from src.core.statuses import format_status_message

        msg = format_status_message(ProjectStatus.NEW, "Test Project")
        assert "Test Project" in msg
        assert "accepted" in msg.lower()
