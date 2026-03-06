import os
import hashlib
import logging
from pathlib import Path
from typing import Dict

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    Language,
)
from config import config

logger = logging.getLogger(__name__)

# Map file extensions to LangChain Language enum
# for smart chunking (PRD §4.1)
EXTENSION_TO_LANGUAGE = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".jsx": Language.JS,
    ".tsx": Language.TS,
    ".go": Language.GO,
    ".java": Language.JAVA,
    ".md": Language.MARKDOWN,
    ".rb": Language.RUBY,
    ".rs": Language.RUST,
    ".php": Language.PHP,
    ".c": Language.C,
    ".cpp": Language.CPP,
    ".cs": Language.CSHARP,
    ".html": Language.HTML,
}

# Extensions without language-specific splitting
GENERIC_EXTENSIONS = {
    ".css", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini",
}


def _file_hash(path: str) -> str:
    """Return SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


class CodeIndexer:
    """Indexes code files into ChromaDB."""

    def __init__(
        self,
        chunk_size: int = config.CHUNK_SIZE,
        chunk_overlap: int = config.CHUNK_OVERLAP,
        batch_size: int = config.BATCH_SIZE,
    ):
        """Initialise the indexer.

        Args:
            chunk_size: Characters per chunk.
            chunk_overlap: Overlap between chunks.
            batch_size: Chunks per upsert batch.
        """
        self.chroma_client = chromadb.PersistentClient(
            path=config.CHROMA_DATA_PATH
        )
        self.embedding_fn = (
            embedding_functions.DefaultEmbeddingFunction()
        )
        self.collection = (
            self.chroma_client.get_or_create_collection(
                name="code_snippets",
                embedding_function=self.embedding_fn,
            )
        )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.batch_size = batch_size

        self.supported_extensions = (
            set(EXTENSION_TO_LANGUAGE.keys())
            | GENERIC_EXTENSIONS
        )
        self.excluded_dirs = {
            "node_modules", ".git", "venv",
            "__pycache__", ".venv", ".tox",
            ".mypy_cache", ".pytest_cache",
            "dist", "build", ".eggs",
            ".idea", ".vscode",
        }

        # In-memory hash cache: file_path -> sha256
        self._hash_cache: Dict[str, str] = {}

    def _get_splitter(
        self, ext: str
    ) -> RecursiveCharacterTextSplitter:
        """Return a language-specific or generic splitter."""
        lang = EXTENSION_TO_LANGUAGE.get(ext)
        if lang:
            return (
                RecursiveCharacterTextSplitter.from_language(
                    language=lang,
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                )
            )
        return RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def index_project_folder(
        self, folder_path: str
    ) -> dict:
        """Traverse folder, chunk files, upsert."""
        logger.info(
            "Indexing project folder: %s", folder_path
        )
        project_name = Path(folder_path).name

        files_to_process = []
        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [
                d for d in dirs
                if d not in self.excluded_dirs
            ]
            for file in files:
                suffix = Path(file).suffix
                if suffix in self.supported_extensions:
                    files_to_process.append(
                        os.path.join(root, file)
                    )

        logger.info(
            "Found %d candidate files.",
            len(files_to_process),
        )

        total_chunks = 0
        skipped = 0
        for file_path in files_to_process:
            try:
                current_hash = _file_hash(file_path)
            except Exception:
                current_hash = None

            cached = self._hash_cache.get(file_path)
            if current_hash and cached == current_hash:
                skipped += 1
                continue

            chunks = self._process_file(
                file_path, project_name
            )
            total_chunks += chunks

            if current_hash:
                self._hash_cache[file_path] = current_hash

        if skipped:
            logger.info(
                "Skipped %d unchanged files.", skipped
            )
        logger.info(
            "Indexing complete. %d chunks upserted.",
            total_chunks,
        )
        return {
            "files_processed": (
                len(files_to_process) - skipped
            ),
            "files_skipped": skipped,
            "chunks_upserted": total_chunks,
        }

    def list_projects(self) -> list[str]:
        """Return unique project names from metadata."""
        try:
            all_meta = self.collection.get(
                include=["metadatas"]
            )
            projects = set()
            for m in (all_meta.get("metadatas") or []):
                if m and m.get("project_name"):
                    projects.add(m["project_name"])
            return sorted(projects)
        except Exception as e:
            logger.error(
                "Error listing projects: %s", e
            )
            return []

    def _process_file(
        self, file_path: str, project_name: str
    ) -> int:
        """Read, chunk, and upsert a single file."""
        try:
            with open(
                file_path, "r", encoding="utf-8"
            ) as f:
                content = f.read()
        except Exception as e:
            logger.warning(
                "Error reading %s: %s", file_path, e
            )
            return 0

        if not content.strip():
            return 0

        ext = Path(file_path).suffix
        splitter = self._get_splitter(ext)
        chunks = splitter.split_text(content)

        if not chunks:
            return 0

        documents = []
        metadatas = []
        ids = []

        current_char_idx = 0
        for i, chunk in enumerate(chunks):
            start_idx = content.find(
                chunk, current_char_idx
            )
            if start_idx == -1:
                start_idx = current_char_idx

            start_line = (
                content.count("\n", 0, start_idx) + 1
            )

            documents.append(chunk)
            metadatas.append({
                "file_path": file_path,
                "start_line": start_line,
                "project_name": project_name,
            })
            ids.append(f"{file_path}_chunk_{i}")

            current_char_idx = (
                start_idx
                + len(chunk)
                - self.chunk_overlap
            )
            if current_char_idx < 0:
                current_char_idx = 0

        # Batch upsert to reduce ChromaDB overhead
        total_upserted = 0
        for start in range(
            0, len(documents), self.batch_size
        ):
            end = start + self.batch_size
            try:
                self.collection.upsert(
                    documents=documents[start:end],
                    metadatas=metadatas[start:end],
                    ids=ids[start:end],
                )
                total_upserted += len(
                    documents[start:end]
                )
            except Exception as e:
                logger.error(
                    "Error upserting batch for %s: %s",
                    file_path, e,
                )

        return total_upserted
