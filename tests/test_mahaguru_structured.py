import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from core.mahaguru_client import MahaguruClient

@pytest.fixture
def mock_config_key():
    """Ensure the API key is set for tests."""
    with patch("config.config.MAHAGURU_API_KEY") as mock_key:
        mock_key.get_secret_value.return_value = "test-key"
        yield mock_key

@pytest.mark.asyncio
async def test_mahaguru_extract_json_plan(mock_config_key):
    """Test that the structured JSON plan is correctly extracted."""
    client = MahaguruClient()
    
    content_with_json = (
        "Here is the plan:\n\n"
        "```json\n"
        "{\n"
        "  \"tasks\": [\n"
        "    {\"file\": \"core/indexer.py\", \"action\": \"modify\", \"description\": \"Add FTS5 support\"}\n"
        "  ]\n"
        "}\n"
        "```\n"
        "Follow these steps."
    )
    
    plan = client._extract_json_plan(content_with_json)
    assert "tasks" in plan
    assert len(plan["tasks"]) == 1
    assert plan["tasks"][0]["file"] == "core/indexer.py"
    assert plan["tasks"][0]["action"] == "modify"

@pytest.mark.asyncio
async def test_mahaguru_extract_invalid_json(mock_config_key):
    """Test handling of invalid JSON in the response."""
    client = MahaguruClient()
    
    content_with_bad_json = (
        "Here is a bad plan:\n"
        "```json\n"
        "{ \"tasks\": [ { \"unclosed\": \"object\" ] }\n"
        "```"
    )
    
    plan = client._extract_json_plan(content_with_bad_json)
    assert plan == {}

@pytest.mark.asyncio
async def test_mahaguru_get_refinement_with_json(mock_config_key):
    """Test that get_refinement successfully handles a response with a JSON plan."""
    client = MahaguruClient()
    
    mock_response_content = (
        "<thinking>\nI need to add FTS5 support.\n</thinking>\n"
        "Plan details here.\n"
        "```json\n"
        "{\"tasks\": [{\"file\": \"test.py\", \"action\": \"create\"}]}\n"
        "```"
    )
    
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": mock_response_content
                }
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data
    mock_response.raise_for_status = lambda: None

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        # Capture logs to verify JSON extraction message
        with patch("core.mahaguru_client.logger.info") as mock_logger_info:
            result, structured_plan = await client.get_refinement("Test JSON extraction")
            
            assert "Plan details here." in result
            assert "```json" in result
            assert "<thinking>" not in result
            
            # Verify structured plan
            assert structured_plan["tasks"][0]["file"] == "test.py"
            
            # Verify that logger.info was called for JSON extraction
            mock_logger_info.assert_any_call("Successfully extracted structured JSON plan from Mahaguru.")

    await client.close()
