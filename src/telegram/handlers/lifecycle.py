from __future__ import annotations

import re
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.core.projects import ProjectManager
from src.integrations.notebooklm.adapter import NotebookLMAdapter
from src.models.material import MaterialType
from src.models.project import ProjectStatus
from src.utils.converters import detect_material_type_from_extension
from src.utils.files import download_telegram_file
from src.utils.logging import logger

# Callback data prefixes
CANCEL_CONFIRM = "cancel_confirm:"
CANCEL_ABORT = "cancel_abort:"
DELETE_CONFIRM = "delete_confirm:"
DELETE_ABORT = "delete_abort:"


def extract_project_reference(text: str) -> Optional[str]:
    """Extract a project name reference from text like 'add to project X'."""
    patterns = [
        r"add\s+(?:this\s+)?(?:to|into)\s+(?:project\s+)?['\"]?(.+?)['\"]?\s*$",
        r"(?:cancel|delete|remove|rename)\s+(?:project\s+)?['\"]?(.+?)['\"]?\s*$",
        r"(?:show|view|details\s+(?:of|for))\s+(?:project\s+)?['\"]?(.+?)['\"]?\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


async def handle_rename(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    manager: ProjectManager,
    text: str,
) -> None:
    """Handle project rename requests."""
    match = re.search(
        r"rename\s+(?:project\s+)?['\"]?(.+?)['\"]?\s+(?:to|as)\s+['\"]?(.+?)['\"]?\s*$",
        text,
        re.IGNORECASE,
    )
    if not match:
        await update.effective_message.reply_text(
            "Please use: rename [project name] to [new name]"
        )
        return

    old_name = match.group(1).strip()
    new_name = match.group(2).strip()
    user_id = str(update.effective_user.id)

    project = manager.find_project_by_name(user_id, old_name)
    if not project:
        await update.effective_message.reply_text(
            f"Could not find a project matching '{old_name}'."
        )
        return

    manager.rename_project(project.project_id, new_name)
    await update.effective_message.reply_text(
        f"Project renamed from '{project.project_name}' to '{new_name}'."
    )


async def handle_cancel_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    manager: ProjectManager,
    project_name: str,
) -> None:
    """Send cancel confirmation with inline buttons."""
    user_id = str(update.effective_user.id)
    project = manager.find_project_by_name(user_id, project_name)

    if not project:
        await update.effective_message.reply_text(
            f"Could not find a project matching '{project_name}'."
        )
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Confirm Cancel", callback_data=f"{CANCEL_CONFIRM}{project.project_id}"),
            InlineKeyboardButton("Keep", callback_data=f"{CANCEL_ABORT}{project.project_id}"),
        ]
    ])
    await update.effective_message.reply_text(
        f"Cancel project '{project.project_name}'?",
        reply_markup=keyboard,
    )


async def handle_delete_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    manager: ProjectManager,
    project_name: str,
) -> None:
    """Send delete confirmation with inline buttons."""
    user_id = str(update.effective_user.id)
    project = manager.find_project_by_name(user_id, project_name)

    if not project:
        await update.effective_message.reply_text(
            f"Could not find a project matching '{project_name}'."
        )
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Confirm Delete", callback_data=f"{DELETE_CONFIRM}{project.project_id}"),
            InlineKeyboardButton("Keep", callback_data=f"{DELETE_ABORT}{project.project_id}"),
        ]
    ])
    await update.effective_message.reply_text(
        f"Delete project '{project.project_name}'? This will remove it from both Supabase and NotebookLM.",
        reply_markup=keyboard,
    )


async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    manager: ProjectManager,
    adapter: NotebookLMAdapter,
) -> None:
    """Handle inline button callbacks for confirmations."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = query.data

    if data.startswith(CANCEL_CONFIRM):
        project_id = data[len(CANCEL_CONFIRM):]
        project = manager.get_project(project_id)
        if project:
            manager.cancel_project(project_id)
            await query.edit_message_text(
                f"Project '{project.project_name}' has been cancelled."
            )
        else:
            await query.edit_message_text("Project not found.")

    elif data.startswith(CANCEL_ABORT):
        await query.edit_message_text("Cancel operation aborted. Project unchanged.")

    elif data.startswith(DELETE_CONFIRM):
        project_id = data[len(DELETE_CONFIRM):]
        project = manager.get_project(project_id)
        if project:
            # Delete from NotebookLM if linked
            if project.notebooklm_project_id and adapter.is_available:
                try:
                    await adapter.delete_project(project.notebooklm_project_id)
                except Exception as e:
                    logger.warning(f"Failed to delete from NotebookLM: {e}")
            manager.delete_project(project_id)
            await query.edit_message_text(
                f"Project '{project.project_name}' has been deleted."
            )
        else:
            await query.edit_message_text("Project not found.")

    elif data.startswith(DELETE_ABORT):
        await query.edit_message_text("Delete operation aborted. Project unchanged.")


async def handle_view_project(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    manager: ProjectManager,
    project_name: str,
) -> None:
    """Show project contents with material details."""
    user_id = str(update.effective_user.id)
    project = manager.find_project_by_name(user_id, project_name)

    if not project:
        await update.effective_message.reply_text(
            f"Could not find a project matching '{project_name}'."
        )
        return

    materials = manager.get_materials(project.project_id)

    text = f"Project: {project.project_name}\n"
    text += f"Status: {project.status.value}\n"
    text += f"Created: {project.created_at.strftime('%Y-%m-%d %H:%M')}\n"
    text += f"Request: {project.original_user_request}\n\n"

    if materials:
        text += f"Materials ({len(materials)}):\n"
        for m in materials:
            text += (
                f"  - {m.display_name}\n"
                f"    Type: {m.material_type.value} | Status: {m.status.value}\n"
                f"    Added: {m.added_at.strftime('%Y-%m-%d %H:%M')}\n"
            )
    else:
        text += "No materials attached."

    await update.effective_message.reply_text(text)


async def handle_add_to_project(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    manager: ProjectManager,
    project_name: str,
) -> None:
    """Add material from current message to an existing project."""
    user_id = str(update.effective_user.id)
    message = update.effective_message
    project = manager.find_project_by_name(user_id, project_name)

    if not project:
        await message.reply_text(
            f"Could not find a project matching '{project_name}'."
        )
        return

    added = 0

    if message.document:
        doc = message.document
        file_name = doc.file_name or f"file_{doc.file_id}"
        local_path = await download_telegram_file(
            context.bot, doc.file_id, file_name
        )
        mat_type = detect_material_type_from_extension(file_name)
        manager.add_material(project.project_id, mat_type, local_path, file_name)
        added += 1

    if message.photo:
        photo = message.photo[-1]
        file_name = f"photo_{photo.file_id}.jpg"
        local_path = await download_telegram_file(
            context.bot, photo.file_id, file_name
        )
        manager.add_material(
            project.project_id, MaterialType.IMAGE, local_path, file_name
        )
        added += 1

    if message.audio:
        audio = message.audio
        file_name = audio.file_name or f"audio_{audio.file_id}.mp3"
        local_path = await download_telegram_file(
            context.bot, audio.file_id, file_name
        )
        manager.add_material(
            project.project_id, MaterialType.AUDIO, local_path, file_name
        )
        added += 1

    if added > 0:
        await message.reply_text(
            f"Added {added} material(s) to project '{project.project_name}'."
        )
    else:
        await message.reply_text("No files found in your message to add.")
