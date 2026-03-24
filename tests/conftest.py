"""Pytest configuration for tests/ directory."""
import os
import pytest
from config import config

# Ignore the dummy_project directory — it contains
# sample files for indexing tests, not actual tests.
collect_ignore_glob = ["dummy_project/*"]

@pytest.fixture(autouse=True)
def setup_test_env(tmp_path):
    """Redirect chroma storage to a temp dir for isolation."""
    # Ensure config resets between tests
    config.CHROMA_DATA_PATH = str(tmp_path / "data")
    config.CHUNKS_STORAGE_PATH = str(tmp_path / "chunks")
    
    # Create the dirs
    os.makedirs(config.CHROMA_DATA_PATH, exist_ok=True)
    os.makedirs(config.CHUNKS_STORAGE_PATH, exist_ok=True)
    
    return tmp_path
