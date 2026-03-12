from src.core.projects import generate_project_name


class TestProjectNaming:
    def test_short_request(self):
        name = generate_project_name("summary of AI")
        assert name == "summary"  # words > 2 chars

    def test_long_request(self):
        name = generate_project_name(
            "Please create a comprehensive summary of the latest research papers about artificial intelligence"
        )
        assert len(name) <= 60

    def test_empty_request(self):
        name = generate_project_name("")
        assert name == "Untitled Research"

    def test_all_short_words(self):
        name = generate_project_name("a b c d e")
        assert name == "a b c"

    def test_normal_request(self):
        name = generate_project_name("make audio review of this paper")
        assert "make" in name
        assert "audio" in name
