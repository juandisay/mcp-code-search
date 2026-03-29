"""Tests for MCP tools defined in main.py."""
import pytest

from api.mcp_tools import (
    get_index_stats,
    index_folder,
    list_indexed_projects,
    semantic_code_search,
)


class TestIndexFolder:
    """Tests for the index_folder MCP tool."""

    @pytest.mark.asyncio
    async def test_invalid_path_returns_error(self):
        """Non-existent path returns error."""
        result = await index_folder(
            "/nonexistent/path/xyz"
        )
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_valid_folder(self, tmp_path):
        """Indexing a valid folder succeeds."""
        sample = tmp_path / "example.py"
        sample.write_text("x = 1\n")
        result = await index_folder(str(tmp_path))
        assert "initiated" in result.lower()


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
        assert "Projects" in result


class TestMCPIntegration:
    """Tests for MCP tool registration and integration."""

    @pytest.mark.asyncio
    async def test_mcp_semantic_search_tool_is_correctly_registered(self):
        """
        Verify that the registered MCP tool returns a string and not None.
        This tests the integration between the function and the FastMCP framework.
        """
        from unittest.mock import MagicMock, patch

        from main import mcp

        # 1. Mock the backend searcher to simulate findings
        mock_searcher = MagicMock()
        # Return a sample result to trigger the return path
        mock_searcher.search.return_value = [{
            "snippet": "test code",
            "file_path": "test.py",
            "start_line": 1,
            "project_name": "test_proj",
            "distance": 0.1
        }]

        # 2. Use a patch to inject the mock
        with patch('api.mcp_tools.get_searcher', return_value=mock_searcher):
            # 3. Call the tool via mcp.call_tool (the official way to invoke it)
            # FastMCP returns a tuple: (list_of_content_objects, extra_metadata_dict)
            content_list, _ = await mcp.call_tool("semantic_code_search", arguments={"query": "test query"})

            # 4. Assert it returns a string with token usage
            assert len(content_list) > 0
            result = content_list[0].text
            assert isinstance(result, str)
            assert "--- Snippet 1" in result
            assert "token usage:" in result
