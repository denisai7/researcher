from __future__ import annotations

import os
import re

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.core.orchestration import ResearchOrchestrator
from src.core.projects import ProjectManager
from src.integrations.notebooklm.adapter import NotebookLMAdapter
from src.models.project import ProjectStatus
from src.telegram.handlers import lifecycle, new_task, search
from src.utils.logging import logger


class ResearcherBot:
    def __init__(self):
        self.project_manager = ProjectManager()
        self.adapter = NotebookLMAdapter()
        self.orchestrator = ResearchOrchestrator(project_manager=self.project_manager)
        self.allowed_user_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID")

    def _is_authorized(self, update: Update) -> bool:
        if not self.allowed_user_id:
            return True  # No restriction configured
        return str(update.effective_user.id) == self.allowed_user_id

    async def _handle_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not self._is_authorized(update):
            await update.effective_message.reply_text("Unauthorized.")
            return
        await update.effective_message.reply_text(
            "Welcome to Researcher! Send me a research request with materials "
            "(files, links, YouTube URLs) and I'll process them through NotebookLM.\n\n"
            "You can:\n"
            "- Send text + files to start a new research\n"
            "- Say 'list projects' to see all projects\n"
            "- Say 'find research about X' to search\n"
            "- Say 'show project X' to view details\n"
            "- Say 'rename X to Y' to rename a project\n"
            "- Say 'add this to project X' with a file\n"
            "- Say 'cancel project X' or 'delete project X'\n"
        )

    async def _route_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Route incoming messages based on intent detection."""
        if not self._is_authorized(update):
            return

        message = update.effective_message
        text = (message.text or message.caption or "").strip()
        text_lower = text.lower()

        # Check for list command
        if re.match(r"^(?:list|show\s+all|my)\s+projects?", text_lower):
            page = 0
            page_match = re.search(r"page\s+(\d+)", text_lower)
            if page_match:
                page = int(page_match.group(1)) - 1
            await search.handle_list(update, context, self.project_manager, page)
            return

        if re.match(r"^(?:next\s+page|show\s+more|more\s+projects)", text_lower):
            # Simple next page - context would track this in production
            await search.handle_list(update, context, self.project_manager, page=1)
            return

        # Check for search intent
        query = search.extract_search_query(text)
        if query:
            await search.handle_search(
                update, context, self.project_manager, query
            )
            return

        # Check for rename intent
        if re.match(r"^rename\s+", text_lower):
            await lifecycle.handle_rename(
                update, context, self.project_manager, text
            )
            return

        # Check for cancel intent
        cancel_match = re.match(r"^cancel\s+(?:project\s+)?(.+)", text_lower)
        if cancel_match:
            name = cancel_match.group(1).strip()
            await lifecycle.handle_cancel_request(
                update, context, self.project_manager, name
            )
            return

        # Check for delete intent
        delete_match = re.match(r"^delete\s+(?:project\s+)?(.+)", text_lower)
        if delete_match:
            name = delete_match.group(1).strip()
            await lifecycle.handle_delete_request(
                update, context, self.project_manager, name
            )
            return

        # Check for view/show project intent
        view_match = re.match(
            r"^(?:show|view|details?\s+(?:of|for))\s+(?:project\s+)?(.+)",
            text_lower,
        )
        if view_match:
            name = view_match.group(1).strip()
            await lifecycle.handle_view_project(
                update, context, self.project_manager, name
            )
            return

        # Check for "add to project X" intent
        add_match = re.match(
            r"^add\s+(?:this\s+)?(?:to|into)\s+(?:project\s+)?(.+)",
            text_lower,
        )
        if add_match:
            name = add_match.group(1).strip()
            await lifecycle.handle_add_to_project(
                update, context, self.project_manager, name
            )
            return

        # Check for follow-up to active context project (24h window)
        if text and not message.document and not message.photo and not message.audio:
            context_project = self.project_manager.get_context_project(
                str(update.effective_user.id)
            )
            if context_project and _is_followup(text_lower):
                # Treat as follow-up: update request and re-process
                self.project_manager.project_repo.update(
                    context_project.project_id,
                    {"original_user_request": text, "status": ProjectStatus.NEW.value},
                )
                context_project.original_user_request = text
                context_project.status = ProjectStatus.NEW
                await message.reply_text(
                    f"Follow-up on '{context_project.project_name}': processing..."
                )

                async def status_cb(pid, status, name):
                    try:
                        from src.core.statuses import format_status_message
                        await message.reply_text(format_status_message(status, name))
                    except Exception:
                        pass

                import asyncio
                asyncio.create_task(
                    new_task._process_and_deliver(
                        self.orchestrator, context_project, message, status_cb
                    )
                )
                return

        # Default: treat as new research task
        await new_task.handle_message(update, context, self.orchestrator)

    async def _handle_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle inline button callbacks."""
        if not self._is_authorized(update):
            return
        await lifecycle.handle_callback(
            update, context, self.project_manager, self.adapter
        )

    async def _post_shutdown(self, application: Application) -> None:
        """Clean up resources on shutdown."""
        logger.info("Shutting down Researcher bot, closing NotebookLM client...")
        await self.adapter.close()

    def build_application(self) -> Application:
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        app = Application.builder().token(token).post_shutdown(self._post_shutdown).build()

        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("help", self._handle_start))
        app.add_handler(CallbackQueryHandler(self._handle_callback))
        app.add_handler(
            MessageHandler(
                filters.ALL & ~filters.COMMAND,
                self._route_message,
            )
        )

        return app

    def run(self) -> None:
        logger.info("Starting Researcher bot...")
        app = self.build_application()
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def _is_followup(text: str) -> bool:
    """Heuristic: detect if the message looks like a follow-up request."""
    followup_patterns = [
        r"^make\s+it",
        r"^now\s+",
        r"^also\s+",
        r"^translate",
        r"^shorter",
        r"^longer",
        r"^change",
        r"^redo",
        r"^try\s+again",
        r"^another",
    ]
    return any(re.match(p, text) for p in followup_patterns)
