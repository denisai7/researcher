from __future__ import annotations

from typing import Optional

from src.models.project import ProjectStatus
from src.utils.logging import logger

STATUS_MESSAGES = {
    ProjectStatus.NEW: "Task accepted. Setting up your research project...",
    ProjectStatus.MATERIALS_PREPARING: "Preparing and uploading your materials...",
    ProjectStatus.SENT_TO_NOTEBOOKLM: "Materials sent to NotebookLM. Processing...",
    ProjectStatus.GENERATING: "Generating your research output...",
    ProjectStatus.COMPLETED: "Research complete! Here are your results.",
    ProjectStatus.ERROR: "An error occurred while processing your request.",
    ProjectStatus.CANCELLED: "Research task has been cancelled.",
}

STATUS_EMOJI = {
    ProjectStatus.NEW: "1",
    ProjectStatus.MATERIALS_PREPARING: "2",
    ProjectStatus.SENT_TO_NOTEBOOKLM: "3",
    ProjectStatus.GENERATING: "4",
    ProjectStatus.COMPLETED: "5",
    ProjectStatus.ERROR: "!",
    ProjectStatus.CANCELLED: "x",
}


def format_status_message(status: ProjectStatus, project_name: str) -> str:
    step = STATUS_EMOJI.get(status, "?")
    msg = STATUS_MESSAGES.get(status, "Processing...")
    return f"[{step}/5] {project_name}: {msg}"


def get_next_status(current: ProjectStatus) -> Optional[ProjectStatus]:
    """Get the next status in the processing pipeline."""
    flow = [
        ProjectStatus.NEW,
        ProjectStatus.MATERIALS_PREPARING,
        ProjectStatus.SENT_TO_NOTEBOOKLM,
        ProjectStatus.GENERATING,
        ProjectStatus.COMPLETED,
    ]
    try:
        idx = flow.index(current)
        if idx + 1 < len(flow):
            return flow[idx + 1]
    except ValueError:
        pass
    return None
