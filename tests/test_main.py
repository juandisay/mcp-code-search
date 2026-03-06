"""Tests for MCP tools defined in main.py."""
from main import (
    semantic_code_search,
    index_folder,
    list_indexed_projects,
    get_index_stats,
)


class TestIndexFolder:
    """Tests for the index_folder MCP tool."""

    def test_invalid_path_returns_error(self):
        """Non-existent path returns error."""
        result = index_folder(
            "/nonexistent/path/xyz"
        )
        assert "Error" in result

    def test_valid_folder(self, tmp_path):
        """Indexing a valid folder succeeds."""
        sample = tmp_path / "example.py"
        sample.write_text("x = 1\n")
        result = index_folder(str(tmp_path))
        assert "Successfully" in result


class TestSemanticCodeSearch:
    """Tests for semantic_code_search tool."""

    def test_returns_string(self):
        """Search always returns a string."""
        result = semantic_code_search("hello world")
        assert isinstance(result, str)


class TestListIndexedProjects:
    """Tests for list_indexed_projects tool."""

    def test_returns_string(self):
        """Tool returns a string output."""
        result = list_indexed_projects()
        assert isinstance(result, str)


class TestGetIndexStats:
    """Tests for get_index_stats tool."""

    def test_returns_stats(self):
        """Stats output contains key metrics."""
        result = get_index_stats()
        assert "Total indexed chunks" in result
        assert "Collection" in result
