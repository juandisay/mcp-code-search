from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.mcp_tools import request_mahaguru_refinement
from core.context_assembler import ContextAssembler
from main import mcp


@pytest.mark.asyncio
async def test_mahaguru_tool_registration():
    """Verify the tool is registered in the FastMCP instance."""
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    assert "request_mahaguru_refinement" in tools

@pytest.mark.asyncio
async def test_request_mahaguru_refinement_success():
    """Verify tool execution with mocked client."""
    mock_response = "Step 1: Analyzed. Step 2: Refined."

    with patch("core.context_assembler.get_searcher") as mock_get_searcher, \
         patch("core.mahaguru_client.mahaguru_client.get_refinement", new_callable=AsyncMock) as mock_get:

        # Mock searcher to return no results for RAG
        mock_searcher = MagicMock()
        mock_searcher.search.return_value = []
        mock_get_searcher.return_value = mock_searcher

        mock_get.return_value = mock_response

        result = await request_mahaguru_refinement("Test brief")

        assert "MAHAGURU REFINEMENT RESPONSE" in result
        assert mock_response in result
        # Check that it ends with a token summary
        assert "usage" in result.lower()
        # Verify the call includes empty code_context (since RAG returned nothing)
        mock_get.assert_called_once_with("Test brief", code_context="")

@pytest.mark.asyncio
async def test_request_mahaguru_refinement_with_context(tmp_path):
    """Verify tool execution with file context."""
    test_file = tmp_path / "context.py"
    test_file.write_text("print('context')", encoding="utf-8")

    mock_response = "Context analyzed."

    with patch("core.context_assembler.get_searcher") as mock_get_searcher, \
         patch.object(ContextAssembler, 'is_path_safe') as mock_safe, \
         patch("core.mahaguru_client.mahaguru_client.get_refinement", new_callable=AsyncMock) as mock_get:

        # Mock searcher to return no results for RAG
        mock_searcher = MagicMock()
        mock_searcher.search.return_value = []
        mock_get_searcher.return_value = mock_searcher

        # Allow the test file
        mock_safe.return_value = True
        mock_get.return_value = mock_response

        result = await request_mahaguru_refinement("Fix this", relevant_files=[str(test_file)])

        assert mock_response in result
        # Check that the call included the context header and file path
        args, kwargs = mock_get.call_args
        context = kwargs["code_context"]
        assert "File: " in context
        assert str(test_file) in context
        assert "print('context')" in context

@pytest.mark.asyncio
async def test_request_mahaguru_refinement_error():
    """Verify tool execution with error from client."""
    mock_error = "Error: Failed to contact API"

    with patch("core.mahaguru_client.mahaguru_client.get_refinement", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_error

        result = await request_mahaguru_refinement("Test brief")

        assert mock_error in result
        assert "token usage:" in result.lower()
