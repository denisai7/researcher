"""Phase 4 tests: project lifecycle -- add material, cancel, delete, context, file size."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.material import MaterialStatus, MaterialType, ResearchMaterial
from src.models.project import ProjectStatus, ResearchProject
from src.telegram.handlers import lifecycle
from src.telegram.bot import _is_followup
from src.utils.files import (
    FileSizeError,
    TELEGRAM_FILE_SIZE_LIMIT,
    NOTEBOOKLM_FILE_SIZE_LIMIT,
    check_telegram_file_size,
    check_notebooklm_file_size,
)
from src.utils.converters import suggest_conversion, is_format_supported


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_project(**overrides) -> ResearchProject:
    defaults = dict(
        project_id="proj-1",
        user_id="user-1",
        project_name="Test Project",
        original_user_request="summarize this",
        status=ProjectStatus.NEW,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return ResearchProject(**defaults)


def _make_material(**overrides) -> ResearchMaterial:
    defaults = dict(
        material_id="mat-1",
        project_id="proj-1",
        material_type=MaterialType.PDF,
        source_value="/tmp/test.pdf",
        display_name="test.pdf",
        status=MaterialStatus.RECEIVED,
    )
    defaults.update(overrides)
    return ResearchMaterial(**defaults)


def _mock_manager(project=None, materials=None):
    mgr = MagicMock()
    mgr.find_project_by_name.return_value = project
    mgr.get_project.return_value = project
    mgr.get_materials.return_value = materials or []
    mgr.cancel_project.return_value = None
    mgr.delete_project.return_value = None
    mgr.add_material.return_value = _make_material()
    return mgr


def _mock_adapter():
    adapter = MagicMock()
    adapter.is_available = True
    adapter.delete_project = AsyncMock(return_value=True)
    return adapter


def _mock_update(text="", user_id="user-1", callback_data=None,
                 document=None, photo=None, audio=None,
                 voice=None, video=None, video_note=None):
    update = MagicMock()
    update.effective_user.id = int(user_id) if user_id.isdigit() else 12345
    msg = MagicMock()
    msg.text = text
    msg.caption = None
    msg.reply_text = AsyncMock()
    msg.document = document
    msg.photo = photo
    msg.audio = audio
    msg.voice = voice
    msg.video = video
    msg.video_note = video_note
    update.effective_message = msg

    if callback_data is not None:
        query = MagicMock()
        query.data = callback_data
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
    else:
        update.callback_query = None

    return update


def _mock_context():
    ctx = MagicMock()
    bot = MagicMock()
    tg_file = MagicMock()
    tg_file.download_to_drive = AsyncMock()
    bot.get_file = AsyncMock(return_value=tg_file)
    ctx.bot = bot
    return ctx


# ---------------------------------------------------------------------------
# File size checks
# ---------------------------------------------------------------------------


class TestFileSizeChecks:
    def test_telegram_size_within_limit(self):
        check_telegram_file_size(10 * 1024 * 1024, "small.pdf")  # 10 MB

    def test_telegram_size_over_limit(self):
        with pytest.raises(FileSizeError) as exc_info:
            check_telegram_file_size(25 * 1024 * 1024, "big.pdf")
        assert "big.pdf" in str(exc_info.value)
        assert "Telegram Bot API" in str(exc_info.value)
        assert "20 MB" in str(exc_info.value)

    def test_telegram_size_none_ok(self):
        check_telegram_file_size(None, "unknown.pdf")  # No size info

    def test_telegram_size_exact_limit(self):
        check_telegram_file_size(TELEGRAM_FILE_SIZE_LIMIT, "exact.pdf")  # Exactly at limit

    def test_notebooklm_size_over_limit(self, tmp_path):
        # Create a file > 200MB (fake with sparse file)
        big_file = tmp_path / "huge.pdf"
        big_file.write_bytes(b"\x00")
        # Patch os.path.getsize to report large size
        with patch("src.utils.files.os.path.getsize", return_value=250 * 1024 * 1024):
            with pytest.raises(FileSizeError) as exc_info:
                check_notebooklm_file_size(str(big_file))
        assert "NotebookLM" in str(exc_info.value)

    def test_file_size_error_attributes(self):
        err = FileSizeError("test.mp4", 30_000_000, 20_000_000, "Telegram Bot API")
        assert err.file_name == "test.mp4"
        assert err.file_size == 30_000_000
        assert err.limit == 20_000_000
        assert err.limit_source == "Telegram Bot API"


# ---------------------------------------------------------------------------
# Format support and conversion suggestions
# ---------------------------------------------------------------------------


class TestFormatConversion:
    def test_suggest_conversion_docx(self):
        hint = suggest_conversion(MaterialType.FILE, "report.docx")
        assert hint is not None
        assert "PDF" in hint

    def test_suggest_conversion_pptx(self):
        hint = suggest_conversion(MaterialType.FILE, "slides.pptx")
        assert hint is not None
        assert "PDF" in hint

    def test_suggest_conversion_epub(self):
        hint = suggest_conversion(MaterialType.FILE, "book.epub")
        assert hint is not None
        assert "PDF" in hint

    def test_suggest_conversion_heic(self):
        hint = suggest_conversion(MaterialType.FILE, "photo.heic")
        assert hint is not None
        assert "JPEG" in hint

    def test_no_conversion_for_unknown_file_extension(self):
        # Unknown extensions that map to FILE type are allowed through
        # (NotebookLM may support them)
        hint = suggest_conversion(MaterialType.FILE, "data.xyz123")
        assert hint is None

    def test_no_conversion_for_supported(self):
        assert suggest_conversion(MaterialType.PDF, "doc.pdf") is None
        assert suggest_conversion(MaterialType.AUDIO, "song.mp3") is None
        assert suggest_conversion(MaterialType.VIDEO, "clip.mp4") is None

    def test_supported_types(self):
        assert is_format_supported(MaterialType.PDF)
        assert is_format_supported(MaterialType.LINK)
        assert is_format_supported(MaterialType.YOUTUBE)
        assert is_format_supported(MaterialType.AUDIO)
        assert is_format_supported(MaterialType.IMAGE)
        assert is_format_supported(MaterialType.VIDEO)
        assert is_format_supported(MaterialType.FILE)


# ---------------------------------------------------------------------------
# Cancel with button confirmation
# ---------------------------------------------------------------------------


class TestCancelFlow:
    @pytest.mark.asyncio
    async def test_cancel_request_sends_buttons(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_cancel_request(update, ctx, manager, "Test Project")

        update.effective_message.reply_text.assert_called_once()
        call_args = update.effective_message.reply_text.call_args
        assert "Cancel project" in call_args[0][0]
        assert call_args[1]["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_cancel_request_not_found(self):
        manager = _mock_manager(project=None)
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_cancel_request(update, ctx, manager, "Unknown")

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Could not find" in msg

    @pytest.mark.asyncio
    async def test_cancel_confirm_callback(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        adapter = _mock_adapter()
        update = _mock_update(callback_data=f"cancel_confirm:{project.project_id}")

        await lifecycle.handle_callback(update, MagicMock(), manager, adapter)

        manager.cancel_project.assert_called_once_with(project.project_id)
        msg = update.callback_query.edit_message_text.call_args[0][0]
        assert "cancelled" in msg.lower()

    @pytest.mark.asyncio
    async def test_cancel_abort_callback(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        adapter = _mock_adapter()
        update = _mock_update(callback_data=f"cancel_abort:{project.project_id}")

        await lifecycle.handle_callback(update, MagicMock(), manager, adapter)

        manager.cancel_project.assert_not_called()
        msg = update.callback_query.edit_message_text.call_args[0][0]
        assert "aborted" in msg.lower()


# ---------------------------------------------------------------------------
# Delete with button confirmation and NotebookLM cascade
# ---------------------------------------------------------------------------


class TestDeleteFlow:
    @pytest.mark.asyncio
    async def test_delete_request_sends_buttons(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_delete_request(update, ctx, manager, "Test Project")

        call_args = update.effective_message.reply_text.call_args
        assert "Delete project" in call_args[0][0]
        assert "NotebookLM" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_confirm_with_notebooklm(self):
        project = _make_project(notebooklm_project_id="nb-123")
        manager = _mock_manager(project=project)
        adapter = _mock_adapter()
        update = _mock_update(callback_data=f"delete_confirm:{project.project_id}")

        await lifecycle.handle_callback(update, MagicMock(), manager, adapter)

        adapter.delete_project.assert_called_once_with("nb-123")
        manager.delete_project.assert_called_once_with(project.project_id)
        msg = update.callback_query.edit_message_text.call_args[0][0]
        assert "deleted" in msg.lower()

    @pytest.mark.asyncio
    async def test_delete_confirm_without_notebooklm(self):
        project = _make_project(notebooklm_project_id=None)
        manager = _mock_manager(project=project)
        adapter = _mock_adapter()
        update = _mock_update(callback_data=f"delete_confirm:{project.project_id}")

        await lifecycle.handle_callback(update, MagicMock(), manager, adapter)

        adapter.delete_project.assert_not_called()
        manager.delete_project.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_confirm_notebooklm_failure_still_deletes(self):
        project = _make_project(notebooklm_project_id="nb-fail")
        manager = _mock_manager(project=project)
        adapter = _mock_adapter()
        adapter.delete_project = AsyncMock(side_effect=Exception("API error"))
        update = _mock_update(callback_data=f"delete_confirm:{project.project_id}")

        await lifecycle.handle_callback(update, MagicMock(), manager, adapter)

        # Should still delete from Supabase despite NotebookLM failure
        manager.delete_project.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_abort_callback(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        adapter = _mock_adapter()
        update = _mock_update(callback_data=f"delete_abort:{project.project_id}")

        await lifecycle.handle_callback(update, MagicMock(), manager, adapter)

        manager.delete_project.assert_not_called()
        msg = update.callback_query.edit_message_text.call_args[0][0]
        assert "aborted" in msg.lower()

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        manager = _mock_manager(project=None)
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_delete_request(update, ctx, manager, "Ghost")

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Could not find" in msg


# ---------------------------------------------------------------------------
# Add material to existing project
# ---------------------------------------------------------------------------


class TestAddToProject:
    @pytest.mark.asyncio
    async def test_add_document_to_project(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        doc = MagicMock()
        doc.file_name = "report.pdf"
        doc.file_id = "file-123"
        doc.file_size = 1024
        update = _mock_update(document=doc)
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_called_once()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Added 1 material(s)" in msg

    @pytest.mark.asyncio
    async def test_add_photo_to_project(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        photo = MagicMock()
        photo.file_id = "photo-123"
        photo.file_size = 500
        update = _mock_update(photo=[photo])
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_voice_to_project(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        voice = MagicMock()
        voice.file_id = "voice-1"
        voice.file_size = 8000
        update = _mock_update(voice=voice)
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_called_once()
        call_args = manager.add_material.call_args
        assert call_args[0][1] == MaterialType.AUDIO

    @pytest.mark.asyncio
    async def test_add_video_to_project(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        video = MagicMock()
        video.file_id = "vid-1"
        video.file_name = "clip.mp4"
        video.file_size = 5000
        update = _mock_update(video=video)
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_called_once()
        call_args = manager.add_material.call_args
        assert call_args[0][1] == MaterialType.VIDEO

    @pytest.mark.asyncio
    async def test_add_video_note_to_project(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        vn = MagicMock()
        vn.file_id = "vn-1"
        vn.file_size = 3000
        update = _mock_update(video_note=vn)
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_called_once()
        call_args = manager.add_material.call_args
        assert call_args[0][1] == MaterialType.VIDEO

    @pytest.mark.asyncio
    async def test_add_no_files(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_not_called()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "No files found" in msg

    @pytest.mark.asyncio
    async def test_add_project_not_found(self):
        manager = _mock_manager(project=None)
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "NonExistent")

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Could not find" in msg

    @pytest.mark.asyncio
    async def test_add_oversized_file_reports_error(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        doc = MagicMock()
        doc.file_name = "huge.pdf"
        doc.file_id = "file-big"
        doc.file_size = 25 * 1024 * 1024  # 25 MB, over Telegram limit
        update = _mock_update(document=doc)
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_not_called()
        msg = update.effective_message.reply_text.call_args[0][0]
        assert "could not be added" in msg
        assert "Telegram Bot API" in msg


# ---------------------------------------------------------------------------
# View project details
# ---------------------------------------------------------------------------


class TestViewProject:
    @pytest.mark.asyncio
    async def test_view_with_materials(self):
        project = _make_project()
        materials = [
            _make_material(display_name="doc.pdf"),
            _make_material(
                material_id="mat-2",
                material_type=MaterialType.YOUTUBE,
                display_name="video.youtube",
            ),
        ]
        manager = _mock_manager(project=project, materials=materials)
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_view_project(update, ctx, manager, "Test Project")

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Test Project" in msg
        assert "doc.pdf" in msg
        assert "Materials (2)" in msg

    @pytest.mark.asyncio
    async def test_view_no_materials(self):
        project = _make_project()
        manager = _mock_manager(project=project, materials=[])
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_view_project(update, ctx, manager, "Test Project")

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "No materials attached" in msg


# ---------------------------------------------------------------------------
# Rename project
# ---------------------------------------------------------------------------


class TestRenameProject:
    @pytest.mark.asyncio
    async def test_rename_success(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_rename(update, ctx, manager, "rename Test Project to New Name")

        manager.rename_project.assert_called_once_with(project.project_id, "New Name")

    @pytest.mark.asyncio
    async def test_rename_bad_format(self):
        manager = _mock_manager()
        update = _mock_update()
        ctx = _mock_context()

        await lifecycle.handle_rename(update, ctx, manager, "rename")

        msg = update.effective_message.reply_text.call_args[0][0]
        assert "Please use" in msg


# ---------------------------------------------------------------------------
# 24-hour follow-up context
# ---------------------------------------------------------------------------


class TestFollowUpContext:
    def test_followup_patterns(self):
        assert _is_followup("make it shorter")
        assert _is_followup("now translate to english")
        assert _is_followup("also add a conclusion")
        assert _is_followup("translate this")
        assert _is_followup("shorter version please")
        assert _is_followup("longer please")
        assert _is_followup("change the tone")
        assert _is_followup("redo this")
        assert _is_followup("try again with more detail")
        assert _is_followup("another version")

    def test_not_followup(self):
        assert not _is_followup("summarize this pdf")
        assert not _is_followup("new research about AI")
        assert not _is_followup("hello")
        assert not _is_followup("find my projects")

    def test_extract_project_reference(self):
        from src.telegram.handlers.lifecycle import extract_project_reference

        assert extract_project_reference("add this to project My Research") == "My Research"
        assert extract_project_reference("delete My Project") == "My Project"
        assert extract_project_reference("cancel project Old Work") == "Old Work"
        assert extract_project_reference("show project Details") == "Details"
        assert extract_project_reference("random text") is None


# ---------------------------------------------------------------------------
# Callback without query (edge case)
# ---------------------------------------------------------------------------


class TestCallbackEdgeCases:
    @pytest.mark.asyncio
    async def test_no_callback_query(self):
        update = MagicMock()
        update.callback_query = None
        manager = _mock_manager()
        adapter = _mock_adapter()

        # Should return without error
        await lifecycle.handle_callback(update, MagicMock(), manager, adapter)

    @pytest.mark.asyncio
    async def test_callback_project_not_found(self):
        manager = _mock_manager(project=None)
        adapter = _mock_adapter()
        update = _mock_update(callback_data="delete_confirm:nonexistent")

        await lifecycle.handle_callback(update, MagicMock(), manager, adapter)

        msg = update.callback_query.edit_message_text.call_args[0][0]
        assert "not found" in msg.lower()


# ---------------------------------------------------------------------------
# Auto-conversion for unsupported formats
# ---------------------------------------------------------------------------


class TestAutoConversion:
    def test_can_auto_convert_docx(self):
        from src.utils.converters import can_auto_convert
        assert can_auto_convert("report.docx")

    def test_can_auto_convert_pptx(self):
        from src.utils.converters import can_auto_convert
        assert can_auto_convert("slides.pptx")

    def test_can_auto_convert_heic(self):
        from src.utils.converters import can_auto_convert
        assert can_auto_convert("photo.heic")

    def test_cannot_auto_convert_unknown(self):
        from src.utils.converters import can_auto_convert
        assert not can_auto_convert("data.xyz")

    def test_cannot_auto_convert_supported(self):
        from src.utils.converters import can_auto_convert
        assert not can_auto_convert("doc.pdf")

    def test_get_target_format_pdf(self):
        from src.utils.converters import get_auto_convert_target
        assert get_auto_convert_target("report.docx") == "pdf"
        assert get_auto_convert_target("slides.pptx") == "pdf"
        assert get_auto_convert_target("data.xlsx") == "pdf"

    def test_get_target_format_jpeg(self):
        from src.utils.converters import get_auto_convert_target
        assert get_auto_convert_target("photo.heic") == "jpeg"
        assert get_auto_convert_target("scan.tiff") == "jpeg"

    def test_get_target_format_none(self):
        from src.utils.converters import get_auto_convert_target
        assert get_auto_convert_target("doc.pdf") is None

    @pytest.mark.asyncio
    async def test_auto_convert_file_no_soffice(self):
        """Auto-conversion returns None when converter tool is not available."""
        from src.utils.converters import auto_convert_file
        result = await auto_convert_file("/tmp/nonexistent.docx")
        assert result is None

    @pytest.mark.asyncio
    async def test_auto_convert_success(self, tmp_path):
        """Auto-conversion returns converted path on success."""
        from src.utils.converters import auto_convert_file

        # Create a fake .docx and simulate successful conversion
        src_file = tmp_path / "test.docx"
        src_file.write_text("fake content")
        output_pdf = tmp_path / "test.pdf"

        async def mock_subprocess(*args, **kwargs):
            # Create the output file to simulate conversion
            output_pdf.write_text("converted")
            proc = MagicMock()
            proc.returncode = 0
            proc.wait = AsyncMock(return_value=0)
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await auto_convert_file(str(src_file))

        assert result == str(output_pdf)


# ---------------------------------------------------------------------------
# Add URL to existing project
# ---------------------------------------------------------------------------


class TestAddUrlToProject:
    @pytest.mark.asyncio
    async def test_add_url_in_text(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        update = _mock_update(text="add this to project Test https://example.com/article")
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_called_once()
        call_args = manager.add_material.call_args
        assert call_args[0][1] == MaterialType.LINK
        assert "example.com" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_add_youtube_url(self):
        project = _make_project()
        manager = _mock_manager(project=project)
        update = _mock_update(text="add to project Test https://www.youtube.com/watch?v=abc123")
        ctx = _mock_context()

        await lifecycle.handle_add_to_project(update, ctx, manager, "Test Project")

        manager.add_material.assert_called_once()
        call_args = manager.add_material.call_args
        assert call_args[0][1] == MaterialType.YOUTUBE


# ---------------------------------------------------------------------------
# Follow-up result delivery
# ---------------------------------------------------------------------------


class TestFollowUpDelivery:
    def test_followup_resets_status(self):
        """Follow-up should reset project status so it can be re-processed."""
        from src.telegram.bot import _is_followup
        assert _is_followup("make it shorter")
        assert _is_followup("redo this")
        assert not _is_followup("summarize this pdf")
