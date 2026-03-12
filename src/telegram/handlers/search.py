from __future__ import annotations

import re
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.core.projects import ProjectManager
from src.models.project import ResearchProject
from src.utils.logging import logger

SEARCH_PATTERNS = [
    r"(?:find|search|look\s*(?:for|up))\s+(?:for\s+)?(?:my\s+)?(?:research\s+)?(?:about\s+)?(.+)",
    r"(?:where\s+is|show\s+me)\s+(?:my\s+)?(?:research\s+)?(?:about\s+)?(.+)",
]


def extract_search_query(text: str) -> Optional[str]:
    """Extract the search query from natural language."""
    for pattern in SEARCH_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def format_project_list(projects: list[ResearchProject], manager: ProjectManager) -> str:
    if not projects:
        return "No projects found."

    lines = []
    for i, p in enumerate(projects, 1):
        mat_count = manager.count_materials(p.project_id)
        snippet = p.original_user_request[:80]
        if len(p.original_user_request) > 80:
            snippet += "..."
        lines.append(
            f"{i}. {p.project_name}\n"
            f"   Status: {p.status.value} | Materials: {mat_count}\n"
            f"   Created: {p.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"   Request: {snippet}"
        )
    return "\n\n".join(lines)


async def handle_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    manager: ProjectManager,
    query: str,
) -> None:
    """Search for projects matching a query."""
    user_id = str(update.effective_user.id)

    projects = manager.search_projects(user_id, query=query)

    if not projects:
        await update.effective_message.reply_text(
            f"No projects found matching '{query}'."
        )
        return

    result_text = f"Found {len(projects)} project(s):\n\n"
    result_text += format_project_list(projects, manager)
    await update.effective_message.reply_text(result_text)


async def handle_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    manager: ProjectManager,
    page: int = 0,
) -> None:
    """List all projects with pagination."""
    user_id = str(update.effective_user.id)
    page_size = 10
    offset = page * page_size

    total = manager.count_projects(user_id)
    projects = manager.list_projects(user_id, limit=page_size, offset=offset)

    if not projects:
        await update.effective_message.reply_text("You have no research projects yet.")
        return

    result_text = f"Your research projects ({offset + 1}-{offset + len(projects)} of {total}):\n\n"
    result_text += format_project_list(projects, manager)

    if offset + page_size < total:
        result_text += f"\n\nSay 'show more' or 'next page' to see more."

    await update.effective_message.reply_text(result_text)
