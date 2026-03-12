"""Tests for the new_task Telegram handler -- Phase 1 end-to-end flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.orchestration import ResearchOrchestrator
from src.models.material import MaterialType
from src.models.project import ProjectStatus, ResearchProject


def _make_update(text=None, caption=None, has_document=False, has_photo=False):
    """Create a mock Telegram Update."""
    message = AsyncMock()
    message.text = text
    message.caption = caption
    message.document = None
    message.photo = None
    message.audio = None
    message.voice = None
    message.video = None
    message.video_note = None

    if has_document:
        doc = MagicMock()
        doc.file_name = "test.pdf"
        doc.file_id = "file_123"
        doc.file_size = 1024
        message.document = doc

    if has_photo:
        photo = MagicMock()
        photo.file_id = "photo_123"
        photo.file_size = 512
        message.photo = [photo]  # list, last element is largest

    update = MagicMock()
    update.effective_message = message
    update.effective_user.id = 12345
    return update


def _make_orchestrator(is_new=True):
    """Create a mock orchestrator that returns a test project."""
    project = ResearchProject(
        user_id="12345",
        project_name="Test Research",
        original_user_request="test request",
        status=ProjectStatus.NEW,
    )
    orch = MagicMock(spec=ResearchOrchestrator)
    orch.handle_new_message.return_value = (project, is_new)
    # process_project is async -- make it return None to skip delivery
    orch.process_project = AsyncMock(return_value=None)
    return orch, project


class TestHandleMessage:
    @pytest.mark.asyncio
    @patch("src.telegram.handlers.new_task.download_telegram_file", new_callable=AsyncMock)
    async def test_text_message_creates_project(self, mock_download):
        from src.telegram.handlers.new_task import handle_message

        update = _make_update(text="summarize this paper about AI")
        context = MagicMock()
        orch, project = _make_orchestrator(is_new=True)

        await handle_message(update, context, orch)
        # Let background task complete
        await asyncio.sleep(0.05)

        orch.handle_new_message.assert_called_once()
        call_args = orch.handle_new_message.call_args
        assert call_args[0][0] == "12345"  # user_id
        assert call_args[0][1] == "summarize this paper about AI"  # text

    @pytest.mark.asyncio
    @patch("src.telegram.handlers.new_task.download_telegram_file", new_callable=AsyncMock)
    async def test_sends_task_accepted_for_new_project(self, mock_download):
        from src.telegram.handlers.new_task import handle_message

        update = _make_update(text="research request")
        context = MagicMock()
        orch, project = _make_orchestrator(is_new=True)

        await handle_message(update, context, orch)
        await asyncio.sleep(0.05)

        # First reply_text call should be the "task accepted" message
        first_call = update.effective_message.reply_text.call_args_list[0]
        reply_text = first_call[0][0]
        assert "accepted" in reply_text.lower()
        assert project.project_name in reply_text

    @pytest.mark.asyncio
    @patch("src.telegram.handlers.new_task.download_telegram_file", new_callable=AsyncMock)
    async def test_sends_added_for_grouped_message(self, mock_download):
        from src.telegram.handlers.new_task import handle_message

        update = _make_update(text="more info here")
        context = MagicMock()
        orch, project = _make_orchestrator(is_new=False)

        await handle_message(update, context, orch)
        await asyncio.sleep(0.05)

        first_call = update.effective_message.reply_text.call_args_list[0]
        reply_text = first_call[0][0]
        assert "Added to project" in reply_text

    @pytest.mark.asyncio
    @patch("src.telegram.handlers.new_task.download_telegram_file", new_callable=AsyncMock)
    async def test_document_is_downloaded_and_added(self, mock_download):
        from src.telegram.handlers.new_task import handle_message

        mock_download.return_value = "/tmp/test.pdf"
        update = _make_update(caption="review this", has_document=True)
        context = MagicMock()
        orch, project = _make_orchestrator(is_new=True)

        await handle_message(update, context, orch)
        await asyncio.sleep(0.05)

        mock_download.assert_called_once_with(context.bot, "file_123", "test.pdf")
        # Materials should be passed to orchestrator
        call_args = orch.handle_new_message.call_args
        materials = call_args[0][2]
        assert len(materials) == 1
        assert materials[0]["type"] == MaterialType.PDF
        assert materials[0]["source"] == "/tmp/test.pdf"

    @pytest.mark.asyncio
    @patch("src.telegram.handlers.new_task.download_telegram_file", new_callable=AsyncMock)
    async def test_photo_is_downloaded_and_added(self, mock_download):
        from src.telegram.handlers.new_task import handle_message

        mock_download.return_value = "/tmp/photo_photo_123.jpg"
        update = _make_update(caption="what is this?", has_photo=True)
        context = MagicMock()
        orch, project = _make_orchestrator(is_new=True)

        await handle_message(update, context, orch)
        await asyncio.sleep(0.05)

        call_args = orch.handle_new_message.call_args
        materials = call_args[0][2]
        assert len(materials) == 1
        assert materials[0]["type"] == MaterialType.IMAGE

    @pytest.mark.asyncio
    async def test_empty_message_ignored(self):
        from src.telegram.handlers.new_task import handle_message

        update = _make_update(text=None)
        context = MagicMock()
        orch, _ = _make_orchestrator()

        await handle_message(update, context, orch)

        orch.handle_new_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_effective_message_returns(self):
        from src.telegram.handlers.new_task import handle_message

        update = MagicMock()
        update.effective_message = None
        context = MagicMock()
        orch, _ = _make_orchestrator()

        await handle_message(update, context, orch)

        orch.handle_new_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.telegram.handlers.new_task.download_telegram_file", new_callable=AsyncMock)
    async def test_text_and_document_together(self, mock_download):
        from src.telegram.handlers.new_task import handle_message

        mock_download.return_value = "/tmp/paper.pdf"
        update = _make_update(caption="summarize this paper", has_document=True)
        update.effective_message.document.file_name = "paper.pdf"
        context = MagicMock()
        orch, project = _make_orchestrator(is_new=True)

        await handle_message(update, context, orch)
        await asyncio.sleep(0.05)

        call_args = orch.handle_new_message.call_args
        assert call_args[0][1] == "summarize this paper"  # text
        assert len(call_args[0][2]) == 1  # 1 material
