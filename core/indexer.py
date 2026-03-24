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
from core.token_manager import token_manager

logger = logging.getLogger(__name__)

from core.ast_chunker import ASTChunker, EXTENSION_TO_TS_LANG

# Supported extensions for AST chunking
AST_SUPPORTED_EXTENSIONS = set(EXTENSION_TO_TS_LANG.keys())

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

        self.chunks_dir = Path(config.CHUNKS_STORAGE_PATH)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

        self.supported_extensions = (
            AST_SUPPORTED_EXTENSIONS
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

    def _get_splitter(self, ext: str):
        """Return an AST-aware chunker or a generic fallback splitter."""
        if ext in AST_SUPPORTED_EXTENSIONS:
            return ASTChunker(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                extension=ext
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
        total_tokens = 0
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

            chunks, tokens = self._process_file(
                file_path, project_name
            )
            total_chunks += chunks
            total_tokens += tokens

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
            "total_tokens": total_tokens,
        }

    def delete_file(self, file_path: str):
        """Remove all chunks associated with a specific file_path."""
        query_result = self.collection.get(
            where={"file_path": file_path},
            include=["metadatas"]
        )
        
        if not query_result or not query_result.get("ids"):
            return
            
        ids_to_delete = query_result["ids"]
        metadatas = query_result["metadatas"]
        
        # Delete from ChromaDB
        self.collection.delete(ids=ids_to_delete)
        logger.info("Deleted %d chunks for %s from ChromaDB", len(ids_to_delete), file_path)
        
        # Delete chunk text files from blob storage
        for meta in (metadatas or []):
            if meta and meta.get("chunk_file"):
                chunk_path = Path(meta["chunk_file"])
                if chunk_path.exists():
                    try:
                        chunk_path.unlink()
                    except Exception as e:
                        logger.warning("Failed to delete chunk file %s: %s", chunk_path, e)
                        
        # Remove from hash cache if present
        self._hash_cache.pop(file_path, None)

    def update_file(self, file_path: str, project_name: str) -> dict:
        """Clean up old chunks and re-index a single file."""
        self.delete_file(file_path)
        
        if not os.path.exists(file_path):
            return {"chunks_upserted": 0, "total_tokens": 0}
            
        try:
            current_hash = _file_hash(file_path)
        except Exception:
            current_hash = None
            
        chunks, tokens = self._process_file(file_path, project_name)
        
        if current_hash:
            self._hash_cache[file_path] = current_hash
            
        return {"chunks_upserted": chunks, "total_tokens": tokens}

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
    ) -> tuple[int, int]:
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
            return 0, 0

        if not content.strip():
            return 0, 0

        ext = Path(file_path).suffix
        splitter = self._get_splitter(ext)
        chunks = splitter.split_text(content)

        if not chunks:
            return 0, 0

        documents = []
        metadatas = []
        ids = []
        chunk_file_paths = []

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

            # Save chunk to disk instead of storage in SQLite
            chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()
            chunk_file_path = self.chunks_dir / f"{chunk_hash}.txt"
            
            # Write chunk if it doesn't exist
            if not chunk_file_path.exists():
                with open(chunk_file_path, "w", encoding="utf-8") as f:
                    f.write(chunk)

            # documents.append(chunk) # We'll compute embeddings instead of storing docs
            metadatas.append({
                "file_path": file_path,
                "start_line": start_line,
                "project_name": project_name,
                "chunk_file": str(chunk_file_path),
            })
            ids.append(f"{file_path}_chunk_{i}")
            documents.append(chunk) # still need this for embedding generation

            current_char_idx = (
                start_idx
                + len(chunk)
                - self.chunk_overlap
            )
            if current_char_idx < 0:
                current_char_idx = 0

        # Batch upsert to reduce ChromaDB overhead
        total_upserted = 0
        total_tokens = 0
        for start in range(
            0, len(documents), self.batch_size
        ):
            end = start + self.batch_size
            batch_docs = documents[start:end]
            batch_metas = metadatas[start:end]
            batch_ids = ids[start:end]
            
            try:
                # Count tokens for this batch
                for doc in batch_docs:
                    total_tokens += token_manager.count_tokens(doc)

                # Generate embeddings manually
                embeddings = self.embedding_fn(batch_docs)
                
                # Upsert WITHOUT documents to save space in SQLite
                self.collection.upsert(
                    ids=batch_ids,
                    embeddings=embeddings,
                    metadatas=batch_metas,
                )
                total_upserted += len(batch_ids)
            except Exception as e:
                logger.error(
                    "Error upserting batch for %s: %s",
                    file_path, e,
                )

        return total_upserted, total_tokens
