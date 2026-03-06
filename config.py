from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

# Project root directory (where this file lives)
_PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # ChromaDB Data Storage Directory
    CHROMA_DATA_PATH: str = str(_PROJECT_ROOT / "data")

    # Optional: Automatically index this folder on startup
    PROJECT_FOLDER_TO_INDEX: str = ""

    # Indexer tuning
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    BATCH_SIZE: int = 100

    # Searcher tuning (0.0=exact, 2.0=no filter)
    MAX_DISTANCE: float = 2.0

    model_config = {"env_file": ".env"}

    @field_validator("CHROMA_DATA_PATH")
    @classmethod
    def resolve_chroma_path(cls, v: str) -> str:
        """Resolve relative paths against project root."""
        p = Path(v)
        if not p.is_absolute():
            return str(_PROJECT_ROOT / p)
        return v


config = Settings()
