import os
import json
import hashlib
import logging
import threading
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Any

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import config
from core.token_manager import token_manager
from core.ast_chunker import ASTChunker, EXTENSION_TO_TS_LANG

logger = logging.getLogger(__name__)

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
    try:
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        return h.hexdigest()
    except Exception:
        return ""


def _get_file_stats(path: str) -> str:
    """Return a string representing file stats (mtime + size) for fast checking."""
    try:
        stat = os.stat(path)
        return f"{stat.st_mtime}_{stat.st_size}"
    except Exception:
        return ""


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
        from chromadb.config import Settings
        self.chroma_client = chromadb.PersistentClient(
            path=config.CHROMA_DATA_PATH,
            settings=Settings(anonymized_telemetry=False)
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

        # Persistent hash cache: file_path -> stats_string (mtime_size)
        self.hash_cache_path = Path(config.CHROMA_DATA_PATH) / "hash_cache.json"
        self._hash_cache: Dict[str, str] = self._load_hash_cache()
        
        # SQLite global writer lock for thread safety (avoid "database is locked" and leaks)
        self._db_lock = threading.Lock()
        self._cache_lock = threading.Lock()  # Lock for self._hash_cache and hash_cache.json

    def _load_hash_cache(self) -> Dict[str, str]:
        """Load hash cache from disk."""
        if self.hash_cache_path.exists():
            try:
                with open(self.hash_cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load hash cache: %s", e)
        return {}

    def _save_hash_cache(self):
        """Save the hash cache to a JSON file (Thread-Safe)."""
        with self._cache_lock:
            try:
                with open(self.hash_cache_path, "w", encoding="utf-8") as f:
                    json.dump(self._hash_cache, f, indent=2)
            except Exception as e:
                logger.error("Failed to save hash cache: %s", e)

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

    def index_project_folder(self, folder_path: str) -> dict:
        """Traverse folder, chunk files in parallel with thread-safe DB locked updates."""
        folder_path = os.path.abspath(folder_path)
        logger.info("Indexing project folder: %s", folder_path)
        project_name = Path(folder_path).name

        files_to_process = []
        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            for file in files:
                suffix = Path(file).suffix
                if suffix in self.supported_extensions:
                    files_to_process.append(os.path.join(root, file))

        logger.info("Found %d candidate files.", len(files_to_process))

        # Remove stale files from index
        folder_prefix = os.path.join(folder_path, "")
        files_to_process_set = set(files_to_process)
        stale_files = [
            fp for fp in list(self._hash_cache.keys())
            if fp.startswith(folder_prefix) and fp not in files_to_process_set
        ]
        for stale_fp in stale_files:
            self.delete_file(stale_fp, save_cache=False)
        if stale_files:
            self._save_hash_cache()

        total_chunks = 0
        total_tokens = 0
        files_indexed = 0
        skipped = 0

        # Filter out unchanged files first
        to_index = []
        for fp in files_to_process:
            current_stats = _get_file_stats(fp)
            if self._hash_cache.get(fp) == current_stats:
                skipped += 1
                continue
            to_index.append((fp, current_stats))

        if not to_index:
            logger.info("Nothing to index. All %d files skipped.", skipped)
            return {
                "files_processed": 0,
                "files_skipped": skipped,
                "chunks_upserted": 0,
                "total_tokens": 0,
            }

        # Process changed/new files in parallel
        max_workers = config.INDEXING_MAX_WORKERS
        logger.info("Indexing %d files using %d workers", len(to_index), max_workers)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self._process_file_worker, fp, project_name): (fp, stats) 
                for fp, stats in to_index
            }
            
            for future in concurrent.futures.as_completed(future_to_file):
                fp, stats = future_to_file[future]
                try:
                    chunks_count, tokens_count = future.result()
                    total_chunks += chunks_count
                    total_tokens += tokens_count
                    
                    # Store stats even if chunks_count is 0 to avoid re-scanning empty/binary files
                    with self._cache_lock:
                        self._hash_cache[fp] = stats
                    if chunks_count > 0:
                        files_indexed += 1
                except Exception as e:
                    logger.error("Error processing file %s: %s", fp, e)

        self._save_hash_cache()
        logger.info("Indexing complete. %d chunks upserted.", total_chunks)

        return {
            "files_processed": files_indexed,
            "files_skipped": skipped,
            "chunks_upserted": total_chunks,
            "total_tokens": total_tokens,
        }

    def _process_file_worker(self, file_path: str, project_name: str) -> Tuple[int, int]:
        """Worker function for individual file processing."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return 0, 0

        if not content.strip():
            return 0, 0

        ext = Path(file_path).suffix
        splitter = self._get_splitter(ext)
        chunks = splitter.split_text(content)

        if not chunks:
            return 0, 0

        # Synchronous delete with global lock to avoid SQLite contention
        with self._db_lock:
            self._delete_file_no_lock(file_path)

        prepared_ids = []
        prepared_metas = []
        prepared_docs = []
        
        current_char_idx = 0
        total_tokens_file = 0

        for i, chunk in enumerate(chunks):
            start_idx = content.find(chunk, current_char_idx)
            if start_idx == -1:
                start_idx = current_char_idx
            
            start_line = content.count("\n", 0, start_idx) + 1
            
            unique_str = f"{file_path}_{i}_{chunk}"
            chunk_hash = hashlib.sha256(unique_str.encode()).hexdigest()
            chunk_file_path = self.chunks_dir / f"{chunk_hash}.txt"

            if not chunk_file_path.exists():
                try:
                    with open(chunk_file_path, "w", encoding="utf-8") as f:
                        f.write(chunk)
                except Exception:
                    continue

            prepared_metas.append({
                "file_path": file_path,
                "extension": ext,
                "start_line": start_line,
                "project_name": project_name,
                "chunk_file": str(chunk_file_path),
            })
            prepared_ids.append(f"{file_path}_chunk_{i}")
            prepared_docs.append(chunk)
            total_tokens_file += token_manager.count_tokens(chunk)

            current_char_idx = max(0, start_idx + len(chunk) - self.chunk_overlap)

        # Batch upsert securely via lock
        for start in range(0, len(prepared_docs), self.batch_size):
            end = start + self.batch_size
            batch_docs = prepared_docs[start:end]
            
            try:
                # Heavy weight operations (embedding generation) outside the lock
                batch_embeddings = self.embedding_fn(batch_docs)
                
                # Critical section: writing to SQLite
                with self._db_lock:
                    self.collection.upsert(
                        ids=prepared_ids[start:end],
                        embeddings=batch_embeddings,
                        metadatas=prepared_metas[start:end]
                    )
            except Exception as e:
                logger.error("Failed to index chunks for %s: %s", file_path, e)

        return len(prepared_ids), total_tokens_file

    def _delete_file_no_lock(self, file_path: str):
        """Internal sync delete for single file (expects caller to hold _db_lock)."""
        query_result = self.collection.get(where={"file_path": file_path})
        if query_result and query_result.get("ids"):
            self.collection.delete(ids=query_result["ids"])

    def delete_file(self, file_path: str, save_cache: bool = True):
        """Remove a file from the index (Thread-Safe)."""
        file_path = os.path.abspath(file_path)
        
        # Update cache
        with self._cache_lock:
            self._hash_cache.pop(file_path, None)
        
        # Remove from vector DB
        with self._db_lock:
            self._delete_file_no_lock(file_path)
            
        if save_cache:
            self._save_hash_cache()

    def update_file(self, file_path: str, project_name: str) -> dict:
        """Update a single file in the index (Watcher-friendly and Thread-Safe)."""
        # Normalize and check existence
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            self.delete_file(file_path)
            return {"chunks_upserted": 0, "total_tokens": 0}

        stats = _get_file_stats(file_path)
        with self._cache_lock:
            self._hash_cache[file_path] = stats
        
        # Process in isolation
        chunks, tokens = self._process_file_worker(file_path, project_name)
        self._save_hash_cache()
        
        return {"chunks_upserted": chunks, "total_tokens": tokens}

    def list_projects(self) -> List[str]:
        """Return unique project names from metadata."""
        projects = set()
        try:
            offset = 0
            limit = 5000
            while True:
                with self._db_lock:
                    results = self.collection.get(
                        include=["metadatas"],
                        limit=limit,
                        offset=offset
                    )
                if not results or not results.get("metadatas"):
                    break

                for m in results["metadatas"]:
                    if m and m.get("project_name"):
                        projects.add(m["project_name"])

                if len(results["metadatas"]) < limit:
                    break
                offset += limit
            return sorted(list(projects))
        except Exception:
            return []

    def delete_project(self, project_name: str) -> dict:
        """Remove all chunks and related data for a specific project with lock."""
        logger.info("Deleting project: %s", project_name)
        
        with self._db_lock:
            results = self.collection.get(
                where={"project_name": project_name},
                include=["metadatas"]
            )

        if not results or not results.get("ids"):
            return {"deleted_chunks": 0, "deleted_files": 0}

        ids_to_delete = results["ids"]
        metadatas = results["metadatas"]
        file_paths = {m["file_path"] for m in metadatas if m and m.get("file_path")}

        with self._db_lock:
            for i in range(0, len(ids_to_delete), 10000):
                self.collection.delete(ids=ids_to_delete[i:i+10000])

        for m in (metadatas or []):
            if m and m.get("chunk_file"):
                p = Path(m["chunk_file"])
                if p.exists():
                    p.unlink(missing_ok=True)

        with self._cache_lock:
            for fp in file_paths:
                self._hash_cache.pop(fp, None)
        
        self._save_hash_cache()

        return {"deleted_chunks": len(ids_to_delete), "deleted_files": len(file_paths)}
