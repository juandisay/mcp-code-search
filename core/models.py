from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class IndexingTask:
    """Represents a file to be processed by a Producer."""
    file_path: str
    stats_str: str
    project_name: str

@dataclass
class ProcessedChunkBatch:
    """Represents a batch of chunks processed from a single file, ready for the Consumer."""
    file_path: str
    stats_str: str
    ids: List[str]
    embeddings: List[List[float]]
    metadatas: List[Dict[str, Any]]
    docs: List[str]
    total_tokens: int
