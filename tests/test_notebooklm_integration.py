"""Tests for NotebookLM integration layer (Phase 2).

All external calls are mocked -- these tests verify the adapter logic,
intent detection, material routing, result construction, and the
end-to-end task processor pipeline with status callbacks.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.integrations.notebooklm.adapter import (
    NotebookLMAdapter,
    detect_intent,
    INTENT_MAP,
    DEFAULT_ACTION,
)
from src.models.material import MaterialType, MaterialStatus, ResearchMaterial
from src.models.result import ResearchResult


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

class TestIntentDetection:
    def test_audio_keywords(self):
        assert detect_intent("make an audio review") == "audio_overview"
        assert detect_intent("create a podcast") == "audio_overview"
        assert detect_intent("I want to listen to this") == "audio_overview"

    def test_summary_keywords(self):
        assert detect_intent("summarize this paper") == "summary"
        assert detect_intent("give me an overview") == "summary"
        assert detect_intent("write a brief") == "summary"
        assert detect_intent("prepare a briefing") == "summary"

    def test_study_guide_keywords(self):
        assert detect_intent("create a study guide") == "study_guide"
        assert detect_intent("help me study this") == "study_guide"

    def test_default_action(self):
        assert detect_intent("process these files") == DEFAULT_ACTION
        assert detect_intent("do something with this") == DEFAULT_ACTION

    def test_case_insensitive(self):
        assert detect_intent("MAKE AN AUDIO") == "audio_overview"
        assert detect_intent("Summarize This") == "summary"


# ---------------------------------------------------------------------------
# Adapter: material upload routing
# ---------------------------------------------------------------------------

class TestAdapterUploadRouting:
    def setup_method(self):
        self.adapter = NotebookLMAdapter()
        self.adapter.client = MagicMock()
        self.adapter.client.add_source_url = AsyncMock(return_value=True)
        self.adapter.client.add_source_file = AsyncMock(return_value=True)

    def _make_material(self, mat_type, source="test_source"):
        return ResearchMaterial(
            material_id="m1",
            project_id="p1",
            material_type=mat_type,
            source_value=source,
            display_name="test",
        )

    @pytest.mark.asyncio
    async def test_link_uses_add_source_url(self):
        mat = self._make_material(MaterialType.LINK, "https://example.com")
        result = await self.adapter.upload_material("nb1", mat)
        assert result is True
        self.adapter.client.add_source_url.assert_awaited_once_with(
            "nb1", "https://example.com"
        )

    @pytest.mark.asyncio
    async def test_youtube_uses_add_source_url(self):
        mat = self._make_material(
            MaterialType.YOUTUBE, "https://youtube.com/watch?v=abc"
        )
        result = await self.adapter.upload_material("nb1", mat)
        assert result is True
        self.adapter.client.add_source_url.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pdf_uses_add_source_file(self):
        mat = self._make_material(MaterialType.PDF, "/tmp/doc.pdf")
        result = await self.adapter.upload_material("nb1", mat)
        assert result is True
        self.adapter.client.add_source_file.assert_awaited_once_with(
            "nb1", "/tmp/doc.pdf"
        )

    @pytest.mark.asyncio
    async def test_audio_uses_add_source_file(self):
        mat = self._make_material(MaterialType.AUDIO, "/tmp/audio.mp3")
        result = await self.adapter.upload_material("nb1", mat)
        assert result is True
        self.adapter.client.add_source_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_image_uses_add_source_file(self):
        mat = self._make_material(MaterialType.IMAGE, "/tmp/photo.jpg")
        result = await self.adapter.upload_material("nb1", mat)
        assert result is True
        self.adapter.client.add_source_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_video_uses_add_source_file(self):
        mat = self._make_material(MaterialType.VIDEO, "/tmp/clip.mp4")
        result = await self.adapter.upload_material("nb1", mat)
        assert result is True
        self.adapter.client.add_source_file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_file_uses_add_source_file(self):
        mat = self._make_material(MaterialType.FILE, "/tmp/data.csv")
        result = await self.adapter.upload_material("nb1", mat)
        assert result is True
        self.adapter.client.add_source_file.assert_awaited_once()


# ---------------------------------------------------------------------------
# Adapter: result generation
# ---------------------------------------------------------------------------

class TestAdapterGenerateResult:
    def setup_method(self):
        self.adapter = NotebookLMAdapter()
        self.adapter.client = MagicMock()

    @pytest.mark.asyncio
    async def test_audio_overview_returns_file_result(self):
        self.adapter.client.generate_audio_overview = AsyncMock(
            return_value="/tmp/audio.mp3"
        )
        result = await self.adapter.generate_result("nb1", "audio_overview")
        assert result.result_type == "audio_overview"
        assert result.is_file
        assert result.file_path == "/tmp/audio.mp3"
        assert result.file_name == "audio_overview.mp3"

    @pytest.mark.asyncio
    async def test_summary_returns_text_result(self):
        self.adapter.client.generate_summary = AsyncMock(
            return_value="This is a summary of the materials."
        )
        result = await self.adapter.generate_result("nb1", "summary")
        assert result.result_type == "summary"
        assert result.is_text
        assert "summary" in result.content.lower()

    @pytest.mark.asyncio
    async def test_study_guide_returns_text_result(self):
        self.adapter.client.generate_study_guide = AsyncMock(
            return_value="# Study Guide\n\n1. Key concepts..."
        )
        result = await self.adapter.generate_result("nb1", "study_guide")
        assert result.result_type == "study_guide"
        assert result.is_text
        assert "Study Guide" in result.content

    @pytest.mark.asyncio
    async def test_unknown_action_defaults_to_summary(self):
        self.adapter.client.generate_summary = AsyncMock(
            return_value="Default summary"
        )
        result = await self.adapter.generate_result("nb1", "unknown_action")
        assert result.result_type == "summary"
        self.adapter.client.generate_summary.assert_awaited_once()


# ---------------------------------------------------------------------------
# Adapter: create / delete project
# ---------------------------------------------------------------------------

class TestAdapterProjectLifecycle:
    def setup_method(self):
        self.adapter = NotebookLMAdapter()
        self.adapter.client = MagicMock()

    @pytest.mark.asyncio
    async def test_create_project(self):
        self.adapter.client.create_notebook = AsyncMock(return_value="nb-123")
        result = await self.adapter.create_project("My Research")
        assert result == "nb-123"
        self.adapter.client.create_notebook.assert_awaited_once_with("My Research")

    @pytest.mark.asyncio
    async def test_delete_project(self):
        self.adapter.client.delete_notebook = AsyncMock(return_value=True)
        result = await self.adapter.delete_project("nb-123")
        assert result is True


# ---------------------------------------------------------------------------
# Client wrapper: availability check
# ---------------------------------------------------------------------------

class TestClientAvailability:
    def test_is_available_when_importable(self):
        from src.integrations.notebooklm.client import NotebookLMClientWrapper

        wrapper = NotebookLMClientWrapper()
        # notebooklm is mocked in conftest.py, so it's importable
        assert wrapper.is_available is True


# ---------------------------------------------------------------------------
# End-to-end task processor with mocked adapter
# ---------------------------------------------------------------------------

class TestTaskProcessorPipeline:
    """Test the full pipeline through ResearchTaskProcessor."""

    def setup_method(self):
        from src.models.project import ProjectStatus, ResearchProject
        from src.workers.tasks import ResearchTaskProcessor

        self.project = ResearchProject(
            project_id="p1",
            user_id="u1",
            project_name="Test Research",
            original_user_request="summarize this paper",
            status=ProjectStatus.NEW,
        )

        # Mock project manager
        self.pm = MagicMock()
        self.pm.get_materials.return_value = [
            ResearchMaterial(
                material_id="m1",
                project_id="p1",
                material_type=MaterialType.PDF,
                source_value="/tmp/paper.pdf",
                display_name="paper.pdf",
            )
        ]
        self.pm.update_status = MagicMock()
        self.pm.update_material_status = MagicMock()
        self.pm.update_result = MagicMock()
        self.pm.project_repo = MagicMock()

        # Mock adapter
        self.adapter = MagicMock()
        self.adapter.is_available = True
        self.adapter.create_project = AsyncMock(return_value="nb-1")
        self.adapter.upload_material = AsyncMock(return_value=True)
        self.adapter.generate_result = AsyncMock(
            return_value=ResearchResult(
                result_type="summary",
                content="Paper summary here",
                notebooklm_ref="nb-1",
            )
        )

        self.processor = ResearchTaskProcessor(
            project_manager=self.pm, adapter=self.adapter
        )

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        from src.models.project import ProjectStatus

        statuses_received = []

        async def track_status(project_id, status, project_name):
            statuses_received.append(status)

        result = await self.processor.process_project(
            self.project, status_callback=track_status
        )

        # Verify result
        assert result is not None
        assert result.result_type == "summary"
        assert result.content == "Paper summary here"

        # Verify all 5 status stages were hit
        assert ProjectStatus.MATERIALS_PREPARING in statuses_received
        assert ProjectStatus.SENT_TO_NOTEBOOKLM in statuses_received
        assert ProjectStatus.GENERATING in statuses_received
        assert ProjectStatus.COMPLETED in statuses_received

    @pytest.mark.asyncio
    async def test_pipeline_creates_notebook(self):
        await self.processor.process_project(self.project)
        self.adapter.create_project.assert_awaited_once_with("Test Research")

    @pytest.mark.asyncio
    async def test_pipeline_uploads_materials(self):
        await self.processor.process_project(self.project)
        self.adapter.upload_material.assert_awaited_once()
        args = self.adapter.upload_material.call_args
        assert args[0][0] == "nb-1"  # notebook_id
        assert args[0][1].material_type == MaterialType.PDF

    @pytest.mark.asyncio
    async def test_pipeline_detects_intent_from_request(self):
        await self.processor.process_project(self.project)
        # "summarize this paper" should detect "summary"
        self.adapter.generate_result.assert_awaited_once()
        args = self.adapter.generate_result.call_args
        assert args[0][1] == "summary"  # action

    @pytest.mark.asyncio
    async def test_pipeline_audio_intent(self):
        self.project.original_user_request = "make an audio review of this"
        self.adapter.generate_result = AsyncMock(
            return_value=ResearchResult(
                result_type="audio_overview",
                file_path="/tmp/audio.mp3",
                file_name="audio_overview.mp3",
                notebooklm_ref="nb-1",
            )
        )

        result = await self.processor.process_project(self.project)
        assert result.result_type == "audio_overview"
        assert result.is_file

        args = self.adapter.generate_result.call_args
        assert args[0][1] == "audio_overview"

    @pytest.mark.asyncio
    async def test_pipeline_updates_project_with_result(self):
        await self.processor.process_project(self.project)
        self.pm.update_result.assert_called_once_with(
            "p1",
            result_type="summary",
            result_ref="nb-1",
            result_summary="Paper summary here",
        )

    @pytest.mark.asyncio
    async def test_pipeline_marks_materials_used(self):
        await self.processor.process_project(self.project)
        self.pm.update_material_status.assert_any_call(
            "m1", MaterialStatus.USED_IN_RESULT
        )

    @pytest.mark.asyncio
    async def test_pipeline_stores_notebook_id(self):
        await self.processor.process_project(self.project)
        self.pm.project_repo.update.assert_called_once_with(
            "p1", {"notebooklm_project_id": "nb-1"}
        )

    @pytest.mark.asyncio
    async def test_pipeline_error_when_adapter_unavailable(self):
        from src.models.project import ProjectStatus

        self.adapter.is_available = False

        statuses = []
        async def track(pid, s, pn):
            statuses.append(s)

        result = await self.processor.process_project(
            self.project, status_callback=track
        )
        assert result is None
        assert ProjectStatus.ERROR in statuses

    @pytest.mark.asyncio
    async def test_pipeline_error_when_notebook_creation_fails(self):
        from src.models.project import ProjectStatus

        self.adapter.create_project = AsyncMock(side_effect=Exception("API down"))

        statuses = []
        async def track(pid, s, pn):
            statuses.append(s)

        result = await self.processor.process_project(
            self.project, status_callback=track
        )
        assert result is None
        assert ProjectStatus.ERROR in statuses

    @pytest.mark.asyncio
    async def test_pipeline_collects_upload_errors(self):
        """Materials that fail upload should be tracked in result metadata."""
        from src.models.material import ResearchMaterial

        self.pm.get_materials.return_value = [
            ResearchMaterial(
                material_id="m1",
                project_id="p1",
                material_type=MaterialType.PDF,
                source_value="/tmp/good.pdf",
                display_name="good.pdf",
            ),
            ResearchMaterial(
                material_id="m2",
                project_id="p1",
                material_type=MaterialType.PDF,
                source_value="/tmp/bad.pdf",
                display_name="bad.pdf",
            ),
        ]

        call_count = 0

        async def upload_side_effect(notebook_id, material):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Upload failed")
            return True

        self.adapter.upload_material = AsyncMock(side_effect=upload_side_effect)

        result = await self.processor.process_project(self.project)
        assert result is not None
        assert "upload_errors" in result.metadata
        assert len(result.metadata["upload_errors"]) == 1
        assert "bad.pdf" in result.metadata["upload_errors"][0]

    @pytest.mark.asyncio
    async def test_pipeline_no_status_callback(self):
        """Pipeline works without a status callback."""
        result = await self.processor.process_project(self.project)
        assert result is not None
        assert result.result_type == "summary"


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class TestResearchResult:
    def test_text_result(self):
        r = ResearchResult(result_type="summary", content="Some text")
        assert r.is_text
        assert not r.is_file

    def test_file_result(self):
        r = ResearchResult(
            result_type="audio_overview",
            file_path="/tmp/audio.mp3",
            file_name="audio.mp3",
        )
        assert r.is_file
        assert not r.is_text

    def test_file_with_content_is_file(self):
        """When both content and file_path are set, is_text is False."""
        r = ResearchResult(
            result_type="audio_overview",
            content="transcript",
            file_path="/tmp/audio.mp3",
        )
        assert r.is_file
        assert not r.is_text

    def test_metadata_defaults_empty(self):
        r = ResearchResult(result_type="summary")
        assert r.metadata == {}
