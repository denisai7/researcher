from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from src.core.grouping import MessageGrouper
from src.models.project import ProjectStatus, ResearchProject


class TestMessageGrouper:
    def test_no_active_project(self):
        repo = MagicMock()
        repo.get_recent_for_user.return_value = None
        grouper = MessageGrouper(project_repo=repo)

        should, project = grouper.should_group("user1")
        assert not should
        assert project is None

    def test_active_project_found(self):
        mock_project = ResearchProject(
            user_id="user1",
            project_name="Active Project",
            original_user_request="test",
            status=ProjectStatus.NEW,
        )
        repo = MagicMock()
        repo.get_recent_for_user.return_value = mock_project
        grouper = MessageGrouper(project_repo=repo)

        should, project = grouper.should_group("user1")
        assert should
        assert project is not None
        assert project.project_name == "Active Project"


class TestSearchExtraction:
    def test_find_query(self):
        from src.telegram.handlers.search import extract_search_query

        assert extract_search_query("find my research about AI") == "AI"
        assert extract_search_query("search for machine learning") == "machine learning"

    def test_no_query(self):
        from src.telegram.handlers.search import extract_search_query

        assert extract_search_query("hello world") is None

    def test_show_me_query(self):
        from src.telegram.handlers.search import extract_search_query

        assert extract_search_query("show me research about NLP") == "NLP"


class TestBotFollowupDetection:
    def test_followup_patterns(self):
        from src.telegram.bot import _is_followup

        assert _is_followup("make it shorter")
        assert _is_followup("now translate it")
        assert _is_followup("also add a conclusion")
        assert _is_followup("translate to Spanish")
        assert _is_followup("try again")

    def test_not_followup(self):
        from src.telegram.bot import _is_followup

        assert not _is_followup("summarize this document")
        assert not _is_followup("hello")
        assert not _is_followup("research about AI")
