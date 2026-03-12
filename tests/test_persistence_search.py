"""Tests for Phase 3: Persistence, Search, and Project Listing."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.projects import ProjectManager
from src.models.material import MaterialStatus, MaterialType, ResearchMaterial
from src.models.project import ProjectStatus, ResearchProject


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(
    user_id="user1",
    name="Test Project",
    request="test request",
    status=ProjectStatus.NEW,
    created_at=None,
    **kwargs,
):
    p = ResearchProject(
        user_id=user_id,
        project_name=name,
        original_user_request=request,
        status=status,
        **kwargs,
    )
    if created_at:
        p.created_at = created_at
        p.updated_at = created_at
    return p


def _make_material(
    project_id="proj-1",
    mat_type=MaterialType.PDF,
    source="/tmp/test.pdf",
    name="test.pdf",
    status=MaterialStatus.RECEIVED,
):
    return ResearchMaterial(
        project_id=project_id,
        material_type=mat_type,
        source_value=source,
        display_name=name,
        status=status,
    )


def _make_manager(projects=None, materials=None, material_count=0):
    """Create a ProjectManager with mocked repos."""
    proj_repo = MagicMock()
    mat_repo = MagicMock()

    proj_repo.create.side_effect = lambda p: p
    proj_repo.search.return_value = projects or []
    proj_repo.fulltext_search.return_value = projects or []
    proj_repo.search_by_material.return_value = []
    proj_repo.list_for_user.return_value = projects or []
    proj_repo.count_for_user.return_value = len(projects) if projects else 0
    proj_repo.find_by_name.return_value = (projects[0] if projects else None)
    proj_repo.get_by_id.return_value = (projects[0] if projects else None)
    mat_repo.get_by_project.return_value = materials or []
    mat_repo.count_by_project.return_value = material_count
    mat_repo.create.side_effect = lambda m: m

    return ProjectManager(project_repo=proj_repo, material_repo=mat_repo), proj_repo, mat_repo


def _make_update(text, user_id=12345):
    """Create a mock Telegram Update."""
    message = AsyncMock()
    message.text = text
    message.caption = None
    message.document = None
    message.photo = None
    message.audio = None
    message.voice = None
    message.video = None
    message.video_note = None
    update = MagicMock()
    update.effective_message = message
    update.effective_user.id = user_id
    return update


# ===========================================================================
# 1. Repository-level persistence tests
# ===========================================================================

class TestProjectPersistence:
    def test_create_project_persists_all_fields(self):
        manager, proj_repo, _ = _make_manager()
        project = manager.create_project("user1", "Research about quantum computing")

        proj_repo.create.assert_called_once()
        created = proj_repo.create.call_args[0][0]
        assert created.user_id == "user1"
        assert created.original_user_request == "Research about quantum computing"
        assert created.status == ProjectStatus.NEW
        assert created.project_id  # UUID generated
        assert created.created_at
        assert created.updated_at

    def test_update_status_persists(self):
        manager, proj_repo, _ = _make_manager()
        manager.update_status("proj-1", ProjectStatus.COMPLETED)
        proj_repo.update_status.assert_called_once_with("proj-1", ProjectStatus.COMPLETED)

    def test_update_result_persists_all_fields(self):
        manager, proj_repo, _ = _make_manager()
        manager.update_result("proj-1", "summary", result_ref="nb-123", result_summary="A summary")

        proj_repo.update.assert_called_once()
        updates = proj_repo.update.call_args[0][1]
        assert updates["result_type"] == "summary"
        assert updates["result_ref"] == "nb-123"
        assert updates["result_summary"] == "A summary"
        assert updates["status"] == "completed"

    def test_update_result_truncates_long_summary(self):
        manager, proj_repo, _ = _make_manager()
        long_summary = "x" * 2000
        manager.update_result("proj-1", "summary", result_summary=long_summary)

        updates = proj_repo.update.call_args[0][1]
        assert len(updates["result_summary"]) == 1000

    def test_rename_project(self):
        manager, proj_repo, _ = _make_manager()
        manager.rename_project("proj-1", "New Name")
        proj_repo.update.assert_called_once_with("proj-1", {"project_name": "New Name"})

    def test_cancel_project(self):
        manager, proj_repo, _ = _make_manager()
        manager.cancel_project("proj-1")
        proj_repo.update_status.assert_called_once_with("proj-1", ProjectStatus.CANCELLED)

    def test_delete_project(self):
        manager, proj_repo, _ = _make_manager()
        manager.delete_project("proj-1")
        proj_repo.delete.assert_called_once_with("proj-1")


class TestMaterialPersistence:
    def test_add_material_persists_all_fields(self):
        manager, _, mat_repo = _make_manager()
        material = manager.add_material(
            "proj-1", MaterialType.PDF, "/tmp/paper.pdf", "paper.pdf"
        )

        mat_repo.create.assert_called_once()
        created = mat_repo.create.call_args[0][0]
        assert created.project_id == "proj-1"
        assert created.material_type == MaterialType.PDF
        assert created.source_value == "/tmp/paper.pdf"
        assert created.display_name == "paper.pdf"
        assert created.status == MaterialStatus.RECEIVED

    def test_update_material_status(self):
        manager, _, mat_repo = _make_manager()
        manager.update_material_status("mat-1", MaterialStatus.ADDED_TO_NOTEBOOKLM)
        mat_repo.update_status.assert_called_once_with("mat-1", "added_to_notebooklm")

    def test_get_materials(self):
        materials = [
            _make_material(name="a.pdf"),
            _make_material(name="b.mp3", mat_type=MaterialType.AUDIO),
        ]
        manager, _, _ = _make_manager(materials=materials)
        result = manager.get_materials("proj-1")
        assert len(result) == 2

    def test_count_materials(self):
        manager, _, mat_repo = _make_manager(material_count=5)
        assert manager.count_materials("proj-1") == 5


# ===========================================================================
# 2. Search tests
# ===========================================================================

class TestSearchProjects:
    def test_search_by_query_uses_fulltext_first(self):
        projects = [_make_project(name="AI Research")]
        manager, proj_repo, _ = _make_manager(projects=projects)

        results = manager.search_projects("user1", query="AI")

        proj_repo.fulltext_search.assert_called_once()
        assert len(results) == 1
        assert results[0].project_name == "AI Research"

    def test_search_falls_back_to_ilike_on_fulltext_error(self):
        projects = [_make_project(name="Quantum Paper")]
        manager, proj_repo, _ = _make_manager(projects=projects)
        proj_repo.fulltext_search.side_effect = Exception("FTS not available")

        results = manager.search_projects("user1", query="quantum")

        proj_repo.search.assert_called_once()
        assert len(results) == 1

    def test_search_merges_material_results(self):
        proj_a = _make_project(name="Project A")
        proj_b = _make_project(name="Project B")
        manager, proj_repo, _ = _make_manager(projects=[proj_a])
        proj_repo.search_by_material.return_value = [proj_b]

        results = manager.search_projects("user1", query="paper.pdf")
        assert len(results) == 2

    def test_search_deduplicates_material_results(self):
        proj = _make_project(name="Shared")
        manager, proj_repo, _ = _make_manager(projects=[proj])
        proj_repo.search_by_material.return_value = [proj]  # same project

        results = manager.search_projects("user1", query="test")
        assert len(results) == 1

    def test_search_by_status_only(self):
        projects = [_make_project(status=ProjectStatus.COMPLETED)]
        manager, proj_repo, _ = _make_manager(projects=projects)
        proj_repo.fulltext_search.return_value = []

        results = manager.search_projects("user1", status="completed")

        proj_repo.search.assert_called_once()
        call_kwargs = proj_repo.search.call_args
        assert call_kwargs[0][2] == "completed" or call_kwargs[1].get("status") == "completed"

    def test_search_by_date_range(self):
        projects = [_make_project(name="Recent")]
        manager, proj_repo, _ = _make_manager(projects=projects)
        proj_repo.fulltext_search.return_value = []

        results = manager.search_projects(
            "user1",
            date_from="2025-01-01T00:00:00+00:00",
            date_to="2025-12-31T23:59:59+00:00",
        )
        assert len(results) == 1

    def test_search_no_results(self):
        manager, proj_repo, _ = _make_manager(projects=[])
        proj_repo.search_by_material.return_value = []

        results = manager.search_projects("user1", query="nonexistent")
        assert len(results) == 0


class TestFindByName:
    def test_find_existing_project(self):
        proj = _make_project(name="My AI Research")
        manager, proj_repo, _ = _make_manager(projects=[proj])

        result = manager.find_project_by_name("user1", "AI Research")
        proj_repo.find_by_name.assert_called_once_with("user1", "AI Research")
        assert result is not None

    def test_find_nonexistent_project(self):
        manager, proj_repo, _ = _make_manager(projects=[])
        proj_repo.find_by_name.return_value = None

        result = manager.find_project_by_name("user1", "nope")
        assert result is None


# ===========================================================================
# 3. Search query parsing tests
# ===========================================================================

class TestSearchQueryParsing:
    def test_extract_search_query_find(self):
        from src.telegram.handlers.search import extract_search_query
        assert extract_search_query("find my research about AI") == "AI"

    def test_extract_search_query_search_for(self):
        from src.telegram.handlers.search import extract_search_query
        assert extract_search_query("search for machine learning") == "machine learning"

    def test_extract_search_query_where_is(self):
        from src.telegram.handlers.search import extract_search_query
        assert extract_search_query("where is my research about NLP") == "NLP"

    def test_extract_search_query_no_match(self):
        from src.telegram.handlers.search import extract_search_query
        assert extract_search_query("hello there") is None

    def test_extract_search_query_look_for(self):
        from src.telegram.handlers.search import extract_search_query
        assert extract_search_query("look for quantum computing") == "quantum computing"


class TestParseSearchFilters:
    def test_plain_text_query(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("artificial intelligence")
        assert result.text == "artificial intelligence"
        assert result.status is None
        assert result.date_from is None

    def test_status_filter_completed(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("completed AI research")
        assert result.status == "completed"
        assert result.text  # remaining text after status removed

    def test_status_filter_done(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("done projects about NLP")
        assert result.status == "completed"

    def test_status_filter_failed(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("failed projects")
        assert result.status == "error"

    def test_status_filter_cancelled(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("cancelled research")
        assert result.status == "cancelled"

    def test_date_filter_today(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("AI research today")
        assert result.date_from is not None
        assert result.date_to is None  # today has no end bound
        assert "AI research" in (result.text or "")

    def test_date_filter_yesterday(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("yesterday research")
        assert result.date_from is not None
        assert result.date_to is not None

    def test_date_filter_this_week(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("projects this week")
        assert result.date_from is not None

    def test_combined_status_and_date(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("completed projects today")
        assert result.status == "completed"
        assert result.date_from is not None

    def test_query_only_status_no_text(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("completed")
        assert result.status == "completed"
        # text may be None or empty after cleanup

    def test_in_progress_filter(self):
        from src.telegram.handlers.search import parse_search_filters
        result = parse_search_filters("in progress tasks")
        assert result.status == "generating"


# ===========================================================================
# 4. Project listing tests
# ===========================================================================

class TestProjectListing:
    def test_format_project_list_with_projects(self):
        from src.telegram.handlers.search import format_project_list

        projects = [
            _make_project(name="AI Research", request="Research about AI and ML trends"),
            _make_project(name="NLP Paper", request="Summarize NLP paper", status=ProjectStatus.COMPLETED),
        ]
        manager, _, _ = _make_manager(material_count=3)
        text = format_project_list(projects, manager)

        assert "AI Research" in text
        assert "NLP Paper" in text
        assert "new" in text
        assert "completed" in text
        assert "Materials: 3" in text
        assert "Research about AI" in text

    def test_format_project_list_empty(self):
        from src.telegram.handlers.search import format_project_list
        manager, _, _ = _make_manager()
        assert format_project_list([], manager) == "No projects found."

    def test_format_project_list_truncates_long_request(self):
        from src.telegram.handlers.search import format_project_list

        long_request = "x" * 200
        projects = [_make_project(request=long_request)]
        manager, _, _ = _make_manager(material_count=0)
        text = format_project_list(projects, manager)
        assert "..." in text

    @pytest.mark.asyncio
    async def test_handle_list_shows_projects(self):
        from src.telegram.handlers.search import handle_list

        projects = [
            _make_project(name="Project A"),
            _make_project(name="Project B"),
        ]
        manager, proj_repo, _ = _make_manager(projects=projects)
        proj_repo.count_for_user.return_value = 2
        update = _make_update("list projects")
        context = MagicMock()

        await handle_list(update, context, manager, page=0)

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "Project A" in reply_text
        assert "Project B" in reply_text
        assert "1-2 of 2" in reply_text

    @pytest.mark.asyncio
    async def test_handle_list_empty(self):
        from src.telegram.handlers.search import handle_list

        manager, proj_repo, _ = _make_manager(projects=[])
        proj_repo.count_for_user.return_value = 0
        update = _make_update("list projects")
        context = MagicMock()

        await handle_list(update, context, manager, page=0)

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "no research projects" in reply_text.lower()

    @pytest.mark.asyncio
    async def test_handle_list_pagination_hint(self):
        from src.telegram.handlers.search import handle_list

        projects = [_make_project(name=f"P{i}") for i in range(10)]
        manager, proj_repo, _ = _make_manager(projects=projects, material_count=1)
        proj_repo.count_for_user.return_value = 15  # more than one page

        update = _make_update("list projects")
        context = MagicMock()

        await handle_list(update, context, manager, page=0)

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "show more" in reply_text.lower() or "next page" in reply_text.lower()


# ===========================================================================
# 5. Search handler integration tests
# ===========================================================================

class TestSearchHandler:
    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        from src.telegram.handlers.search import handle_search

        projects = [_make_project(name="Quantum Computing")]
        manager, proj_repo, _ = _make_manager(projects=projects, material_count=2)
        update = _make_update("find research about quantum")
        context = MagicMock()

        await handle_search(update, context, manager, "quantum")

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "Quantum Computing" in reply_text
        assert "1 project(s)" in reply_text

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        from src.telegram.handlers.search import handle_search

        manager, proj_repo, _ = _make_manager(projects=[])
        proj_repo.fulltext_search.return_value = []
        proj_repo.search_by_material.return_value = []

        update = _make_update("find research about nonexistent")
        context = MagicMock()

        await handle_search(update, context, manager, "nonexistent")

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "No projects found" in reply_text

    @pytest.mark.asyncio
    async def test_search_with_status_filter(self):
        from src.telegram.handlers.search import handle_search

        projects = [_make_project(name="Done Project", status=ProjectStatus.COMPLETED)]
        manager, proj_repo, _ = _make_manager(projects=projects, material_count=1)

        update = _make_update("find completed research about AI")
        context = MagicMock()

        await handle_search(update, context, manager, "completed research about AI")

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "status: completed" in reply_text


# ===========================================================================
# 6. Project view / contents tests
# ===========================================================================

class TestProjectView:
    @pytest.mark.asyncio
    async def test_view_project_shows_details(self):
        from src.telegram.handlers.lifecycle import handle_view_project

        proj = _make_project(name="Deep Learning Paper", request="Summarize the DL paper")
        materials = [
            _make_material(project_id=proj.project_id, name="paper.pdf"),
            _make_material(
                project_id=proj.project_id,
                name="notes.txt",
                mat_type=MaterialType.FILE,
                status=MaterialStatus.ADDED_TO_NOTEBOOKLM,
            ),
        ]
        manager, proj_repo, mat_repo = _make_manager(projects=[proj], materials=materials)

        update = _make_update("show project Deep Learning Paper")
        context = MagicMock()

        await handle_view_project(update, context, manager, "Deep Learning Paper")

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "Deep Learning Paper" in reply_text
        assert "new" in reply_text  # status
        assert "paper.pdf" in reply_text
        assert "notes.txt" in reply_text
        assert "Materials (2)" in reply_text
        assert "pdf" in reply_text
        assert "file" in reply_text

    @pytest.mark.asyncio
    async def test_view_project_not_found(self):
        from src.telegram.handlers.lifecycle import handle_view_project

        manager, proj_repo, _ = _make_manager()
        proj_repo.find_by_name.return_value = None

        update = _make_update("show project nonexistent")
        context = MagicMock()

        await handle_view_project(update, context, manager, "nonexistent")

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "Could not find" in reply_text

    @pytest.mark.asyncio
    async def test_view_project_no_materials(self):
        from src.telegram.handlers.lifecycle import handle_view_project

        proj = _make_project(name="Empty Project")
        manager, _, mat_repo = _make_manager(projects=[proj], materials=[])

        update = _make_update("show project Empty Project")
        context = MagicMock()

        await handle_view_project(update, context, manager, "Empty Project")

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "No materials attached" in reply_text


# ===========================================================================
# 7. Project rename tests
# ===========================================================================

class TestProjectRename:
    @pytest.mark.asyncio
    async def test_rename_project(self):
        from src.telegram.handlers.lifecycle import handle_rename

        proj = _make_project(name="Old Name")
        manager, proj_repo, _ = _make_manager(projects=[proj])

        update = _make_update("rename Old Name to New Name")
        context = MagicMock()

        await handle_rename(update, context, manager, "rename Old Name to New Name")

        proj_repo.update.assert_called_once()
        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "renamed" in reply_text.lower()
        assert "New Name" in reply_text

    @pytest.mark.asyncio
    async def test_rename_project_not_found(self):
        from src.telegram.handlers.lifecycle import handle_rename

        manager, proj_repo, _ = _make_manager()
        proj_repo.find_by_name.return_value = None

        update = _make_update("rename Unknown to Something")
        context = MagicMock()

        await handle_rename(update, context, manager, "rename Unknown to Something")

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "Could not find" in reply_text

    @pytest.mark.asyncio
    async def test_rename_bad_format(self):
        from src.telegram.handlers.lifecycle import handle_rename

        manager, _, _ = _make_manager()
        update = _make_update("rename something")
        context = MagicMock()

        await handle_rename(update, context, manager, "rename something")

        reply_text = update.effective_message.reply_text.call_args[0][0]
        assert "Please use" in reply_text


# ===========================================================================
# 8. Repository-level fulltext search test
# ===========================================================================

class TestFulltextSearchRepository:
    def test_fulltext_search_builds_tsquery(self):
        from src.integrations.supabase.repositories import ProjectRepository

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        # Chain mock
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.text_search.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        repo = ProjectRepository.__new__(ProjectRepository)
        repo.client = mock_client

        repo.fulltext_search("user1", "quantum computing")

        mock_table.text_search.assert_called_once_with(
            "search_vector", "quantum & computing"
        )

    def test_fulltext_search_with_filters(self):
        from src.integrations.supabase.repositories import ProjectRepository

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.text_search.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.lte.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        repo = ProjectRepository.__new__(ProjectRepository)
        repo.client = mock_client

        repo.fulltext_search(
            "user1",
            "AI",
            status="completed",
            date_from="2025-01-01",
            date_to="2025-12-31",
        )

        mock_table.text_search.assert_called_once()
        mock_table.gte.assert_called_once_with("created_at", "2025-01-01")
        mock_table.lte.assert_called_once_with("created_at", "2025-12-31")


# ===========================================================================
# 9. Model serialization round-trip tests
# ===========================================================================

class TestModelRoundTrip:
    def test_project_round_trip(self):
        project = _make_project(
            name="Round Trip",
            request="test",
            status=ProjectStatus.COMPLETED,
        )
        project.notebooklm_project_id = "nlm-999"
        project.result_type = "audio_overview"
        project.result_ref = "ref-abc"
        project.result_summary = "A short summary"

        db_dict = project.to_db_dict()
        restored = ResearchProject.from_db_row(db_dict)

        assert restored.project_id == project.project_id
        assert restored.project_name == "Round Trip"
        assert restored.status == ProjectStatus.COMPLETED
        assert restored.notebooklm_project_id == "nlm-999"
        assert restored.result_type == "audio_overview"
        assert restored.result_ref == "ref-abc"
        assert restored.result_summary == "A short summary"

    def test_material_round_trip(self):
        material = _make_material(
            name="video.mp4",
            mat_type=MaterialType.VIDEO,
            source="https://example.com/video.mp4",
            status=MaterialStatus.USED_IN_RESULT,
        )

        db_dict = material.to_db_dict()
        restored = ResearchMaterial.from_db_row(db_dict)

        assert restored.material_id == material.material_id
        assert restored.display_name == "video.mp4"
        assert restored.material_type == MaterialType.VIDEO
        assert restored.status == MaterialStatus.USED_IN_RESULT
