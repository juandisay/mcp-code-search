import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.mahaguru_client import MahaguruClient
from config import config

@pytest.fixture
def mock_config_key():
    """Ensure the API key is set for tests."""
    with patch("config.config.MAHAGURU_API_KEY") as mock_key:
        mock_key.get_secret_value.return_value = "test-key"
        yield mock_key

@pytest.mark.asyncio
async def test_mahaguru_client_success(mock_config_key):
    """Test successful Mahaguru API call with the first model."""
    client = MahaguruClient()
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": "Refined Plan: Step 1, Step 2."
                }
            }
        ]
    }

    # Mock the response object
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data
    mock_response.raise_for_status = lambda: None

    # Mock the internal client's post method
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await client.get_refinement("Bug in indexer")
        
        assert "Refined Plan" in result
        assert mock_post.called
        # Verify it used the first model in the list
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["model"] == config.MODELS[0]
    
    await client.close()

@pytest.mark.asyncio
async def test_mahaguru_auto_switch(mock_config_key):
    """Test that Mahaguru client switches to the second model if the first one fails."""
    client = MahaguruClient()
    
    # First call returns 429, second returns 200
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {
        "choices": [{"message": {"content": "Switch successful"}}]
    }
    mock_response_success.raise_for_status = lambda: None

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_response_429, mock_response_success]

        result = await client.get_refinement("Test switch")
        
        assert result == "Switch successful"
        assert mock_post.call_count == 2
        
        # Verify models used
        calls = mock_post.call_args_list
        assert calls[0].kwargs["json"]["model"] == config.MODELS[0]
        assert calls[1].kwargs["json"]["model"] == config.MODELS[1]
    
    await client.close()

@pytest.mark.asyncio
async def test_mahaguru_client_http_error(mock_config_key):
    """Test handling of HTTP errors when all models fail."""
    client = MahaguruClient()
    
    # All models fail with Connect Error
    with patch.object(client._client, "post", side_effect=Exception("Connect Error")):
        result = await client.get_refinement("Test brief")
        assert "Error: All Mahaguru models failed" in result
        assert "Connect Error" in result
    
    await client.close()

@pytest.mark.asyncio
async def test_mahaguru_client_close(mock_config_key):
    """Verify that close() properly shuts down the internal client."""
    client = MahaguruClient()
    with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_aclose:
        await client.close()
        mock_aclose.assert_called_once()

@pytest.mark.asyncio
async def test_mahaguru_client_bad_format(mock_config_key):
    """Test handling of unexpected JSON format (should keep trying next model)."""
    client = MahaguruClient()
    
    # First model returns bad format, second returns success
    mock_response_bad = MagicMock()
    mock_response_bad.status_code = 200
    mock_response_bad.json.return_value = {"unexpected": "data"}
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {
        "choices": [{"message": {"content": "Success after bad format"}}]
    }
    mock_response_success.raise_for_status = lambda: None

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_response_bad, mock_response_success]

        result = await client.get_refinement("Test bad format")
        assert result == "Success after bad format"
        assert mock_post.call_count == 2
    
    await client.close()
