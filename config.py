import os
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings

# Project root directory (where this file lives)
_PROJECT_ROOT = Path(__file__).resolve().parent


class AppConfig(BaseSettings):
    """Application settings loaded from environment."""

    # ChromaDB Data Storage Directory
    CHROMA_DATA_PATH: str = str(_PROJECT_ROOT / "data")

    # Local storage for text chunks (to keep sqlite file small)
    CHUNKS_STORAGE_PATH: str = str(_PROJECT_ROOT / "data" / "chunks")

    # Optional: Automatically index this folder on startup
    PROJECT_FOLDER_TO_INDEX: str = ""

    # AI Cascading (Mahaguru Model)
    MAHAGURU_API_URL: str = "http://127.0.0.1:8317/v1"
    MAHAGURU_API_KEY: SecretStr | None = None
    MODELS: list[str] = [
        "gemini-3.1-pro-high",
        "gemini-3.1-pro-low",
        "coder-model",
        "claude-opus-4-6-thinking",
        "claude-haiku-4.5",
        "gpt-5.3-codex",
        "deepseek-r1"
    ]

    # Indexer tuning
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    BATCH_SIZE: int = 100
    INDEXING_MAX_WORKERS: int = max(1, os.cpu_count() - 1)
    STATE_DB_NAME: str = "indexer_state.sqlite"

    # Searcher tuning (0.0=exact, 2.0=no filter)
    MAX_DISTANCE: float = 2.0
    INITIAL_RETRIEVAL_COUNT: int = 20
    CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RE_RANK_LIMIT: int = 20
    USE_RERANKER: bool = True
    USE_HYBRID_SEARCH: bool = True
    RRF_K: int = 60

    # Mahaguru RAG Tuning
    MAHAGURU_AUTO_CONTEXT_COUNT: int = 5
    MAHAGURU_API_TIMEOUT: int = 180
    MAHAGURU_API_RETRIES: int = 2

    # Hardening & Security (Pillar III)
    PROJECT_ROOT: Path = _PROJECT_ROOT
    MAX_CONTEXT_FILE_SIZE: int = 100 * 1024  # 100KB per file
    MAX_TOTAL_CONTEXT_TOKENS: int = 30000    # Safeguard for Mahaguru context
    ALLOWED_CONTEXT_ROOTS: list[str] = [str(_PROJECT_ROOT)]

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "extra": "ignore"
    }

    @field_validator("CHROMA_DATA_PATH", "CHUNKS_STORAGE_PATH")
    @classmethod
    def resolve_paths(cls, v: str) -> str:
        """Resolve relative paths against project root."""
        p = Path(v)
        if not p.is_absolute():
            return str(_PROJECT_ROOT / p)
        return v


config = AppConfig()
