import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from main import request_mahaguru_refinement, mcp

@pytest.mark.asyncio
async def test_mahaguru_tool_registration():
    """Verify the tool is registered in the FastMCP instance."""
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    assert "request_mahaguru_refinement" in tools

@pytest.mark.asyncio
async def test_request_mahaguru_refinement_success():
    """Verify tool execution with mocked client."""
    mock_response = "Step 1: Analyzed. Step 2: Refined."
    
    with patch("core.mahaguru_client.mahaguru_client.get_refinement", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        result = await request_mahaguru_refinement("Test brief")
        
        assert "MAHAGURU REFINEMENT RESPONSE" in result
        assert mock_response in result
        assert "token usage:" in result.lower()
        # Verify the call includes code_context=None
        mock_get.assert_called_once_with("Test brief", code_context="")

@pytest.mark.asyncio
async def test_request_mahaguru_refinement_with_context(tmp_path):
    """Verify tool execution with file context."""
    test_file = tmp_path / "context.py"
    test_file.write_text("print('context')", encoding="utf-8")
    
    mock_response = "Context analyzed."
    
    with patch("core.mahaguru_client.mahaguru_client.get_refinement", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        result = await request_mahaguru_refinement("Fix this", relevant_files=[str(test_file)])
        
        assert mock_response in result
        # Check that the call included the context header and file path
        args, kwargs = mock_get.call_args
        assert "File: " in kwargs["code_context"]
        assert str(test_file) in kwargs["code_context"]
        assert "print('context')" in kwargs["code_context"]

@pytest.mark.asyncio
async def test_request_mahaguru_refinement_error():
    """Verify tool execution with error from client."""
    mock_error = "Error: Failed to contact API"
    
    with patch("core.mahaguru_client.mahaguru_client.get_refinement", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_error
        
        result = await request_mahaguru_refinement("Test brief")
        
        assert mock_error in result
        assert "token usage:" in result.lower()
