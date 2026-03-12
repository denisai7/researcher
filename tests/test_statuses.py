from src.core.statuses import format_status_message, get_next_status
from src.models.project import ProjectStatus


class TestStatusMessages:
    def test_format_new(self):
        msg = format_status_message(ProjectStatus.NEW, "My Project")
        assert "My Project" in msg
        assert "accepted" in msg.lower()

    def test_format_completed(self):
        msg = format_status_message(ProjectStatus.COMPLETED, "Test")
        assert "complete" in msg.lower()

    def test_format_error(self):
        msg = format_status_message(ProjectStatus.ERROR, "Test")
        assert "error" in msg.lower()


class TestStatusFlow:
    def test_next_from_new(self):
        assert get_next_status(ProjectStatus.NEW) == ProjectStatus.MATERIALS_PREPARING

    def test_next_from_generating(self):
        assert get_next_status(ProjectStatus.GENERATING) == ProjectStatus.COMPLETED

    def test_next_from_completed(self):
        assert get_next_status(ProjectStatus.COMPLETED) is None

    def test_next_from_error(self):
        assert get_next_status(ProjectStatus.ERROR) is None

    def test_next_from_cancelled(self):
        assert get_next_status(ProjectStatus.CANCELLED) is None
