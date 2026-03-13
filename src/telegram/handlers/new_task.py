from __future__ import annotations

import asyncio
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.core.orchestration import ResearchOrchestrator
from src.core.statuses import format_status_message
from src.models.material import MaterialType
from src.models.project import ProjectStatus
from src.utils.converters import detect_material_type_from_extension
from src.utils.files import FileSizeError, check_telegram_file_size, cleanup_file, download_telegram_file
from src.utils.logging import logger


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    orchestrator: ResearchOrchestrator,
) -> None:
    """Handle any incoming message -- text, file, or mixed."""
    message = update.effective_message
    if not message:
        return

    user_id = str(update.effective_user.id)
    text = message.text or message.caption or ""
    materials = []
    size_errors = []

    # Process attached document
    if message.document:
        doc = message.document
        file_name = doc.file_name or f"file_{doc.file_id}"
        try:
            check_telegram_file_size(doc.file_size, file_name)
            local_path = await download_telegram_file(
                context.bot, doc.file_id, file_name
            )
            mat_type = detect_material_type_from_extension(file_name)
            materials.append(
                {"type": mat_type, "source": local_path, "name": file_name}
            )
        except FileSizeError as e:
            size_errors.append(str(e))

    # Process photo
    if message.photo:
        photo = message.photo[-1]  # largest size
        file_name = f"photo_{photo.file_id}.jpg"
        try:
            check_telegram_file_size(photo.file_size, file_name)
            local_path = await download_telegram_file(
                context.bot, photo.file_id, file_name
            )
            materials.append(
                {"type": MaterialType.IMAGE, "source": local_path, "name": file_name}
            )
        except FileSizeError as e:
            size_errors.append(str(e))

    # Process audio
    if message.audio:
        audio = message.audio
        file_name = audio.file_name or f"audio_{audio.file_id}.mp3"
        try:
            check_telegram_file_size(audio.file_size, file_name)
            local_path = await download_telegram_file(
                context.bot, audio.file_id, file_name
            )
            materials.append(
                {"type": MaterialType.AUDIO, "source": local_path, "name": file_name}
            )
        except FileSizeError as e:
            size_errors.append(str(e))

    # Process voice
    if message.voice:
        voice = message.voice
        file_name = f"voice_{voice.file_id}.ogg"
        try:
            check_telegram_file_size(voice.file_size, file_name)
            local_path = await download_telegram_file(
                context.bot, voice.file_id, file_name
            )
            materials.append(
                {"type": MaterialType.AUDIO, "source": local_path, "name": file_name}
            )
        except FileSizeError as e:
            size_errors.append(str(e))

    # Process video
    if message.video:
        video = message.video
        file_name = video.file_name or f"video_{video.file_id}.mp4"
        try:
            check_telegram_file_size(video.file_size, file_name)
            local_path = await download_telegram_file(
                context.bot, video.file_id, file_name
            )
            materials.append(
                {"type": MaterialType.VIDEO, "source": local_path, "name": file_name}
            )
        except FileSizeError as e:
            size_errors.append(str(e))

    # Process video note
    if message.video_note:
        vn = message.video_note
        file_name = f"videonote_{vn.file_id}.mp4"
        try:
            check_telegram_file_size(vn.file_size, file_name)
            local_path = await download_telegram_file(
                context.bot, vn.file_id, file_name
            )
            materials.append(
                {"type": MaterialType.VIDEO, "source": local_path, "name": file_name}
            )
        except FileSizeError as e:
            size_errors.append(str(e))

    if not text and not materials and not size_errors:
        return

    # Report file size errors immediately
    if size_errors:
        error_msg = "Some files could not be processed:\n" + "\n".join(
            f"- {err}" for err in size_errors
        )
        await message.reply_text(error_msg)
        if not text and not materials:
            return

    project, is_new = orchestrator.handle_new_message(user_id, text, materials)

    if is_new:
        await message.reply_text(
            format_status_message(ProjectStatus.NEW, project.project_name)
        )
    else:
        await message.reply_text(
            f"Added to project: {project.project_name}"
        )

    # Kick off processing in background
    async def status_callback(project_id, status, project_name):
        try:
            await message.reply_text(
                format_status_message(status, project_name)
            )
        except Exception as e:
            logger.warning(f"Failed to send status update: {e}")

    asyncio.create_task(_process_and_deliver(
        orchestrator, project, message, status_callback
    ))


async def _process_and_deliver(orchestrator, project, message, status_callback):
    """Process the project and deliver results."""
    try:
        result = await orchestrator.process_project(project, status_callback)
        if result is None:
            await message.reply_text(
                f"Failed to process project '{project.project_name}'. "
                "Please check your materials and try again."
            )
            return

        # Deliver text content (sent even when file is also present)
        if result.content:
            content = result.content
            while content:
                chunk = content[:4096]
                await message.reply_text(chunk)
                content = content[4096:]

        # Deliver file attachment
        if result.file_path:
            try:
                with open(result.file_path, "rb") as f:
                    if result.result_type == "audio_overview":
                        await message.reply_audio(
                            audio=f,
                            title=result.file_name or "audio_overview.mp3",
                        )
                    else:
                        await message.reply_document(
                            document=f,
                            filename=result.file_name or "result",
                        )
            except Exception as e:
                await message.reply_text(f"Result generated but failed to send file: {e}")
            finally:
                cleanup_file(result.file_path)

        # Report upload errors
        upload_errors = result.metadata.get("upload_errors", [])
        if upload_errors:
            error_msg = "Some materials had issues:\n" + "\n".join(
                f"- {err}" for err in upload_errors
            )
            await message.reply_text(error_msg)

    except Exception as e:
        logger.error(f"Error processing project {project.project_id}: {e}")
        await message.reply_text(
            f"An unexpected error occurred: {e}"
        )
