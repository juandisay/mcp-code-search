import pytest
import asyncio
import re
from unittest.mock import patch, AsyncMock

from api.mcp_tools import request_async_mahaguru_refinement, get_planning_job_result
from core.job_manager import planning_job_manager

# --- Fixtures ---

@pytest.fixture(autouse=True)
def reset_job_manager():
    """
    Auto-use fixture to ensure the singleton job manager is completely 
    clean before and after every test to prevent state pollution.
    """
    planning_job_manager._jobs.clear()
    yield
    planning_job_manager._jobs.clear()

def extract_job_id(response_text: str) -> str:
    """Helper to extract the Job ID from the tool's string response."""
    match = re.search(r"Job ID: (plan_[a-f0-9]+)", response_text)
    assert match is not None, f"Could not find Job ID in response: {response_text}"
    return match.group(1)

# --- Tests ---

@pytest.mark.asyncio
@patch("api.mcp_tools.mahaguru_client.get_refinement", new_callable=AsyncMock)
@patch("api.mcp_tools.context_assembler.assemble_refinement_context")
async def test_request_async_mahaguru_refinement_creation(mock_assemble, mock_get_refinement):
    """Test 1: Verify job creation returns a valid ID and enters 'Running' state."""
    
    # Setup mock to return immediately
    mock_get_refinement.return_value = "Mocked Plan"
    
    response = await request_async_mahaguru_refinement("Test brief", ["file1.py"])
    
    # Verify response format and extract ID
    assert "Background planning job initiated successfully" in response
    job_id = extract_job_id(response)
    
    # Verify internal state
    job_data = planning_job_manager.check_status(job_id)
    assert job_data is not None
    # It might be Completed already if the event loop was fast, 
    # but we primarily care that it was registered.
    assert job_data["status"] in ["Running", "Completed"]
    
    # Allow background task to flush to avoid asyncio warnings
    await asyncio.sleep(0.01)

@pytest.mark.asyncio
@patch("api.mcp_tools.mahaguru_client.get_refinement")
@patch("api.mcp_tools.context_assembler.assemble_refinement_context")
async def test_get_planning_job_result_lifecycle(mock_assemble, mock_get_refinement):
    """
    Test 2: Verify the full lifecycle: Running -> Completed -> Popped.
    Uses an asyncio.Event to deterministically pause the background task.
    """
    release_event = asyncio.Event()

    async def controlled_mock_refinement(*args, **kwargs):
        await release_event.wait() # Pause execution here
        return "--- MAHAGURU REFINEMENT RESPONSE ---\n\nBrilliant Architectural Plan\n\n--- END OF REFINEMENT ---"

    mock_get_refinement.side_effect = controlled_mock_refinement

    # 1. Initiate Job
    response = await request_async_mahaguru_refinement("Design a database")
    job_id = extract_job_id(response)

    # 2. Verify 'Running' state gracefully handles retrieval
    running_result = get_planning_job_result(job_id)
    assert "is still Running" in running_result
    assert "Mahaguru is currently thinking" in running_result

    # 3. Release the background task and yield control to the event loop
    release_event.set()
    await asyncio.sleep(0.05) # Give the background task time to complete

    # 4. Verify 'Completed' state retrieves results
    completed_result = get_planning_job_result(job_id)
    assert "MAHAGURU REFINEMENT RESPONSE" in completed_result
    assert "Brilliant Architectural Plan" in completed_result

    # 5. Verify 'Popping' behavior (memory cleanup)
    popped_result = get_planning_job_result(job_id)
    assert "Error: Job ID" in popped_result
    assert "not found" in popped_result
    
    # Ensure internal registry is empty
    assert planning_job_manager.check_status(job_id) is None

@pytest.mark.asyncio
@patch("api.mcp_tools.mahaguru_client.get_refinement")
@patch("api.mcp_tools.context_assembler.assemble_refinement_context")
async def test_get_planning_job_result_failed(mock_assemble, mock_get_refinement):
    """Test 3: Verify graceful handling of background task exceptions."""
    
    async def failing_mock(*args, **kwargs):
        raise ValueError("Simulated API Timeout")

    mock_get_refinement.side_effect = failing_mock

    response = await request_async_mahaguru_refinement("Will fail")
    job_id = extract_job_id(response)

    # Yield to let the background task fail
    await asyncio.sleep(0.05)

    # Retrieve result
    failed_result = get_planning_job_result(job_id)
    
    assert "Failed" in failed_result
    assert "Simulated API Timeout" in failed_result
    
    # Verify it was popped after failure retrieval
    assert planning_job_manager.check_status(job_id) is None

def test_edge_case_invalid_job_id():
    """Test 4: Verify behavior when requesting a non-existent Job ID."""
    result = get_planning_job_result("plan_invalid123")
    assert "Error: Job ID 'plan_invalid123' not found" in result

@pytest.mark.asyncio
@patch("api.mcp_tools.mahaguru_client.get_refinement", new_callable=AsyncMock)
@patch("api.mcp_tools.context_assembler.assemble_refinement_context")
async def test_edge_case_concurrent_job_creation(mock_assemble, mock_get_refinement):
    """Test 5: Verify thread-safe creation of multiple concurrent jobs."""
    
    # Pause all tasks so they stay in 'Running' state
    release_event = asyncio.Event()
    async def controlled_mock(*args, **kwargs):
        await release_event.wait()
        return "Done"
    mock_get_refinement.side_effect = controlled_mock

    # Create 10 jobs concurrently
    tasks = [
        request_async_mahaguru_refinement(f"Concurrent brief {i}") 
        for i in range(10)
    ]
    responses = await asyncio.gather(*tasks)

    # Extract all IDs
    job_ids = [extract_job_id(res) for res in responses]

    # Verify all IDs are unique
    assert len(set(job_ids)) == 10

    # Verify active jobs count
    active_jobs = planning_job_manager.get_active_jobs()
    assert len(active_jobs) == 10

    # Cleanup: release tasks and let them finish
    release_event.set()
    await asyncio.sleep(0.05)
