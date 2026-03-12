from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.core.projects import ProjectManager
from src.models.project import ProjectStatus, ResearchProject
from src.utils.logging import logger

SEARCH_PATTERNS = [
    r"(?:find|search|look\s*(?:for|up))\s+(?:for\s+)?(?:my\s+)?(?:research\s+)?(?:about\s+)?(.+)",
    r"(?:where\s+is|show\s+me)\s+(?:my\s+)?(?:research\s+)?(?:about\s+)?(.+)",
]

# Status keywords users might say
STATUS_KEYWORDS = {
    "completed": ProjectStatus.COMPLETED.value,
    "complete": ProjectStatus.COMPLETED.value,
    "done": ProjectStatus.COMPLETED.value,
    "finished": ProjectStatus.COMPLETED.value,
    "new": ProjectStatus.NEW.value,
    "pending": ProjectStatus.NEW.value,
    "in progress": ProjectStatus.GENERATING.value,
    "processing": ProjectStatus.GENERATING.value,
    "generating": ProjectStatus.GENERATING.value,
    "failed": ProjectStatus.ERROR.value,
    "error": ProjectStatus.ERROR.value,
    "cancelled": ProjectStatus.CANCELLED.value,
    "canceled": ProjectStatus.CANCELLED.value,
}

# Date range keywords
DATE_KEYWORDS = {
    "today": lambda: (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0), None),
    "yesterday": lambda: (
        (datetime.now(timezone.utc) - timedelta(days=1)).replace(hour=0, minute=0, second=0),
        datetime.now(timezone.utc).replace(hour=0, minute=0, second=0),
    ),
    "this week": lambda: (
        datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday()),
        None,
    ),
    "last week": lambda: (
        datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday() + 7),
        datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday()),
    ),
    "this month": lambda: (
        datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0),
        None,
    ),
}


@dataclass
class ParsedSearchQuery:
    text: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


def extract_search_query(text: str) -> Optional[str]:
    """Extract the search query from natural language."""
    for pattern in SEARCH_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def parse_search_filters(query: str) -> ParsedSearchQuery:
    """Parse status and date filters from a search query string."""
    result = ParsedSearchQuery()
    remaining = query

    # Extract date filters
    for keyword, date_fn in DATE_KEYWORDS.items():
        if keyword in remaining.lower():
            date_from, date_to = date_fn()
            result.date_from = date_from.isoformat()
            if date_to:
                result.date_to = date_to.isoformat()
            remaining = re.sub(re.escape(keyword), "", remaining, flags=re.IGNORECASE).strip()
            break

    # Extract status filters (check multi-word first)
    for keyword, status_val in sorted(STATUS_KEYWORDS.items(), key=lambda x: -len(x[0])):
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, remaining, re.IGNORECASE):
            result.status = status_val
            remaining = re.sub(pattern, "", remaining, flags=re.IGNORECASE).strip()
            break

    # Clean up leftover filler words
    remaining = re.sub(r"\b(?:from|that|are|is|were|projects?)\b", "", remaining, flags=re.IGNORECASE)
    remaining = re.sub(r"\s+", " ", remaining).strip()

    result.text = remaining if remaining else None
    return result


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
    """Search for projects matching a query with optional status/date filters."""
    user_id = str(update.effective_user.id)

    parsed = parse_search_filters(query)

    projects = manager.search_projects(
        user_id,
        query=parsed.text,
        status=parsed.status,
        date_from=parsed.date_from,
        date_to=parsed.date_to,
    )

    if not projects:
        await update.effective_message.reply_text(
            f"No projects found matching '{query}'."
        )
        return

    header = f"Found {len(projects)} project(s)"
    if parsed.status:
        header += f" (status: {parsed.status})"
    header += ":\n\n"
    result_text = header + format_project_list(projects, manager)
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
