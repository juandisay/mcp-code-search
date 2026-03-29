import concurrent.futures
import hashlib
import logging
import os
import queue
import sqlite3
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

if TYPE_CHECKING:
    pass

from core.ast_chunker import EXTENSION_TO_TS_LANG, ASTChunker
from core.db_utils import get_collection_name  # Add this
from core.models import ProcessedChunkBatch
from core.token_manager import token_manager

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
        app_config: Any,
        embedding_fn: Any = None,
    ):
        """Initialise the indexer.

        Args:
            app_config: Application configuration instance.
            embedding_fn: Optional custom embedding function.
        """
        self.config = app_config
        from chromadb.config import Settings
        self.chroma_client = chromadb.PersistentClient(
            path=self.config.CHROMA_DATA_PATH,
            settings=Settings(anonymized_telemetry=False)
        )

        # Dependency Injection for Embedding Function
        self.embedding_fn = (
            embedding_fn or embedding_functions.DefaultEmbeddingFunction()
        )

        # Unified Collection Naming
        coll_name = get_collection_name(self.embedding_fn)

        self.collection = (
            self.chroma_client.get_or_create_collection(
                name=coll_name,
                embedding_function=self.embedding_fn,
            )
        )

        self.chunk_size = self.config.CHUNK_SIZE
        self.chunk_overlap = self.config.CHUNK_OVERLAP
        self.batch_size = self.config.BATCH_SIZE

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

        # SQLite global writer lock for thread safety (avoid "database is locked" and leaks)
        self._db_lock = threading.Lock()

        # State Storage Database (SQLite)
        self.state_db_path = Path(self.config.CHROMA_DATA_PATH) / self.config.STATE_DB_NAME

        # This connection is ONLY for the consumer thread (Pillar I)
        self._writer_db_conn = sqlite3.connect(
            self.state_db_path,
            check_same_thread=False,
            timeout=30.0
        )
        self._init_state_db(self._writer_db_conn)

        # Producer-Consumer Queue (Pillar III)
        self.work_queue = queue.Queue(maxsize=100)
        self._consumer_thread = None
        self._start_consumer()

    def _init_state_db(self, conn: sqlite3.Connection):
        """Initialize the SQLite state database for file tracking using provided connection."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_state (
                file_path TEXT PRIMARY KEY,
                stats_str TEXT NOT NULL,
                last_indexed REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_roots (
                folder_path TEXT PRIMARY KEY,
                last_indexed REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        conn.commit()

    def _get_read_only_conn(self) -> sqlite3.Connection:
        """Create a read-only SQLite connection for safe concurrent access."""
        # URI mode for read-only
        db_uri = f"file:{self.state_db_path}?mode=ro"
        return sqlite3.connect(db_uri, uri=True)

    def _get_all_file_stats(self) -> Dict[str, str]:
        """Fetch all file stats from the state DB using a read-only connection."""
        try:
            with self._get_read_only_conn() as conn:
                cursor = conn.execute("SELECT file_path, stats_str FROM file_state")
                return {row[0]: row[1] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            # Might happen if DB doesn't exist yet, return empty
            return {}

    def _update_file_state(self, conn: sqlite3.Connection, file_path: str, stats_str: str):
        """Update or insert a file's stats using the provided (writer) connection."""
        conn.execute(
            "INSERT OR REPLACE INTO file_state (file_path, stats_str, last_indexed) VALUES (?, ?, ?)",
            (file_path, stats_str, time.time())
        )
        conn.commit()

    def _consumer_loop(self):
        """Single-threaded consumer that batches and writes to ChromaDB and SQLite state."""
        logger.info("Indexer Consumer thread started.")
        while True:
            try:
                # 1. Get task from queue
                batch: ProcessedChunkBatch = self.work_queue.get()
                if batch is None:  # Sentinel to stop
                    self.work_queue.task_done()
                    break

                # 2. Batch write to ChromaDB
                try:
                    # ChromaDB writes still need serialization if shared
                    # SQLite write is via persistent connection (Pillar I)
                    with self._db_lock:
                        self.collection.upsert(
                            ids=batch.ids,
                            embeddings=batch.embeddings,
                            metadatas=batch.metadatas
                        )
                        # 3. Update File State only after DB success
                        self._update_file_state(self._writer_db_conn, batch.file_path, batch.stats_str)
                except Exception as e:
                    logger.error("Consumer failed to write batch for %s: %s", batch.file_path, e)
                finally:
                    self.work_queue.task_done()

            except Exception as e:
                logger.error("Unexpected error in Indexer Consumer loop: %s", e)

        logger.info("Indexer Consumer thread stopped.")

    def _start_consumer(self):
        """Start the consumer thread if not running."""
        if self._consumer_thread is None or not self._consumer_thread.is_alive():
            self._consumer_thread = threading.Thread(target=self._consumer_loop, daemon=True)
            self._consumer_thread.start()

    def _stop_consumer(self):
        """Stop the consumer thread by sending a sentinel."""
        if self._consumer_thread and self._consumer_thread.is_alive():
            self.work_queue.put(None)
            self.work_queue.join()
            self._consumer_thread = None

    def _delete_file_state(self, conn: sqlite3.Connection, file_path: str):
        """Remove a file from the state DB using provided connection."""
        conn.execute("DELETE FROM file_state WHERE file_path = ?", (file_path,))
        conn.commit()

    def shutdown(self):
        """Gracefully stop the indexer and clean up connections (Pillar III Hardening)."""
        logger.info("Stopping CodeIndexer service...")
        try:
            self._stop_consumer()
        except Exception as e:
            logger.error("Error during consumer thread shutdown: %s", e)
        finally:
            if self._writer_db_conn:
                logger.info("Closing SQLite writer connection.")
                try:
                    self._writer_db_conn.close()
                except Exception as e:
                    logger.error("Error closing SQLite connection: %s", e)
                finally:
                    self._writer_db_conn = None
        logger.info("CodeIndexer service stopped.")

    def _add_project_root(self, conn: sqlite3.Connection, folder_path: str):
        """Record an absolute path as an indexed root."""
        conn.execute(
            "INSERT OR REPLACE INTO project_roots (folder_path, last_indexed) VALUES (?, ?)",
            (folder_path, time.time())
        )
        conn.commit()

    def get_indexed_roots(self) -> List[str]:
        """Fetch all indexed project root paths using a read-only connection."""
        try:
            with self._get_read_only_conn() as conn:
                cursor = conn.execute("SELECT folder_path FROM project_roots")
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []

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
        """Traverse folder, chunk files in parallel using Producer-Consumer pattern."""
        folder_path = os.path.abspath(folder_path)
        logger.info("Indexing project folder: %s", folder_path)
        project_name = Path(folder_path).name

        # Record root for Phase 1 security check
        with self._db_lock:
            self._add_project_root(self._writer_db_conn, folder_path)

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
        all_stats = self._get_all_file_stats()
        stale_files = [
            fp for fp in list(all_stats.keys())
            if fp.startswith(folder_prefix) and fp not in set(files_to_process)
        ]
        for stale_fp in stale_files:
            self.delete_file(stale_fp)

        total_chunks = 0
        total_tokens = 0
        files_indexed = 0
        skipped = 0

        # Filter out unchanged files first
        to_index = []
        for fp in files_to_process:
            current_stats = _get_file_stats(fp)
            if all_stats.get(fp) == current_stats:
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

        # Process changed/new files in parallel (Producers)
        max_workers = self.config.INDEXING_MAX_WORKERS
        logger.info("Indexing %d files using %d workers", len(to_index), max_workers)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self._process_file_worker, fp, stats, project_name): fp
                for fp, stats in to_index
            }

            for future in concurrent.futures.as_completed(future_to_file):
                fp = future_to_file[future]
                try:
                    chunks_count, tokens_count = future.result()
                    total_chunks += chunks_count
                    total_tokens += tokens_count
                    if chunks_count > 0:
                        files_indexed += 1
                except Exception as e:
                    logger.error("Error processing file %s: %s", fp, e)

        logger.info("Indexing complete. %d chunks processed.", total_chunks)

        return {
            "files_processed": files_indexed,
            "files_skipped": skipped,
            "chunks_upserted": total_chunks,
            "total_tokens": total_tokens,
        }

    def _process_file_worker(self, file_path: str, stats_str: str, project_name: str) -> Tuple[int, int]:
        """Producer worker: Reads, chunks, and prepares data for the Consumer."""
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

            prepared_metas.append({
                "file_path": file_path,
                "extension": ext,
                "start_line": start_line,
                "project_name": project_name,
                "model": getattr(self.collection, "name", "unknown")
            })
            prepared_ids.append(f"{file_path}_chunk_{i}")
            prepared_docs.append(chunk)
            total_tokens_file += token_manager.count_tokens(chunk)

            current_char_idx = max(0, start_idx + len(chunk) - self.chunk_overlap)

        # 3. Generate Embeddings (Heavy I/O/CPU) outside the Consumer
        try:
            embeddings = self.embedding_fn(prepared_docs)

            # 4. Push to Consumer Queue
            batch = ProcessedChunkBatch(
                file_path=file_path,
                stats_str=stats_str,
                ids=prepared_ids,
                embeddings=embeddings,
                metadatas=prepared_metas,
                docs=prepared_docs,
                total_tokens=total_tokens_file
            )
            self.work_queue.put(batch)
            return len(prepared_ids), total_tokens_file
        except Exception as e:
            logger.error("Failed to generate embeddings for %s: %s", file_path, e)
            return 0, 0

    def _delete_file_no_lock(self, file_path: str):
        """Internal sync delete for single file (expects caller to hold _db_lock)."""
        query_result = self.collection.get(where={"file_path": file_path})
        if query_result and query_result.get("ids"):
            self.collection.delete(ids=query_result["ids"])

    def delete_file(self, file_path: str):
        """Remove a file from the index (Thread-Safe)."""
        file_path = os.path.abspath(file_path)
        logger.info("Deleting file from index: %s", file_path)

        # Remove from vector DB and SQLite state
        with self._db_lock:
            self._delete_file_no_lock(file_path)
            self._delete_file_state(self._writer_db_conn, file_path)

    def update_file(self, file_path: str, project_name: str) -> dict:
        """Update/Re-index a single file (Thread-Safe). Guard against non-existent paths."""
        file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            logger.warning("update_file called on non-existent path: %s. Removing from index.", file_path)
            self.delete_file(file_path)
            return {"chunks_upserted": 0, "total_tokens": 0}

        # Pillar I: Ensure atomic update (delete then process)
        with self._db_lock:
             self._delete_file_no_lock(file_path)
             # State will be upserted in process_file_worker

        stats = _get_file_stats(file_path)
        chunks, tokens = self._process_file_worker(file_path, stats, project_name)

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
        """Remove all chunks and related data for a specific project."""
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

            for i in range(0, len(ids_to_delete), 10000):
                self.collection.delete(ids=ids_to_delete[i:i+10000])

            # Remove from project_roots if we can identify the folder
            # For simplicity, we keep project_roots entries unless someone manually purges,
            # or we could try matching folder_path by identifying all remaining and finding min prefix.
            # However, file_paths cleanup takes care of file-level state.

            for fp in file_paths:
                self._delete_file_state(self._writer_db_conn, fp)

        return {"deleted_chunks": len(ids_to_delete), "deleted_files": len(file_paths)}
