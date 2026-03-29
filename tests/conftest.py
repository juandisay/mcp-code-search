import pytest

from config import AppConfig


@pytest.fixture(scope="session")
def app_config():
    """Provides a session-scoped application configuration instance for tests.
    
    This ensures all tests use a consistent configuration object, 
    matching the Dependency Injection pattern used in the core logic.
    """
    return AppConfig()
