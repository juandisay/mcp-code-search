import concurrent.futures
import hashlib
import logging
import os
import queue
import shutil
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

        # Dependency Injection for Embedding Function
        self.embedding_fn = (
            embedding_fn or embedding_functions.DefaultEmbeddingFunction()
        )

        # Initialize ChromaDB with recovery logic (Mahaguru Pattern)
        self._init_chromadb_with_recovery()

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

    def _init_chromadb_with_recovery(self):
        """Initialize ChromaDB with a fallback to wipe the data directory if it's corrupted."""
        os.makedirs(self.config.CHROMA_DATA_PATH, exist_ok=True)
        from chromadb.config import Settings

        try:
            self.chroma_client = chromadb.PersistentClient(
                path=self.config.CHROMA_DATA_PATH,
                settings=Settings(anonymized_telemetry=False)
            )
            coll_name = get_collection_name(self.embedding_fn)
            self.collection = self.chroma_client.get_or_create_collection(
                name=coll_name,
                embedding_function=self.embedding_fn,
            )
            # Perform a small connectivity check
            self.collection.count()

            # SCHEMA GUARANTEE (Mahaguru Pattern)
            # Force ChromaDB to create internal SQLite tables (e.g. 'embeddings') immediately
            try:
                self.collection.add(
                    ids=["__init_check__"],
                    documents=["init"],
                    metadatas=[{"type": "init"}]
                )
                self.collection.delete(ids=["__init_check__"])
                logger.info("ChromaDB schema creation guaranteed.")
            except Exception as schema_err:
                logger.warning("Schema guarantee check skipped or failed: %s", schema_err)

            logger.info("ChromaDB initialized successfully.")
        except Exception as e:
            logger.error("ChromaDB corruption or initialization fault detected: %s", e)
            logger.warning("Attempting automatic rebuild of the database environment...")

            # Close existing connection if any
            self.chroma_client = None

            # WIPE the directory (Safest recovery for derived data)
            if os.path.exists(self.config.CHROMA_DATA_PATH):
                try:
                    shutil.rmtree(self.config.CHROMA_DATA_PATH, ignore_errors=True)
                except Exception as wipe_err:
                    logger.error("Failed to wipe data directory: %s", wipe_err)

            os.makedirs(self.config.CHROMA_DATA_PATH, exist_ok=True)

            # RETRY
            self.chroma_client = chromadb.PersistentClient(
                path=self.config.CHROMA_DATA_PATH,
                settings=Settings(anonymized_telemetry=False)
            )
            coll_name = get_collection_name(self.embedding_fn)
            self.collection = self.chroma_client.get_or_create_collection(
                name=coll_name,
                embedding_function=self.embedding_fn,
            )
            logger.info("ChromaDB environment successfully rebuilt and initialized.")

    def _init_state_db(self, conn: sqlite3.Connection):
        """Initialize the SQLite state database for file tracking using provided connection."""
        conn.execute("PRAGMA journal_mode=WAL;")
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

        # Priority 1: Hybrid Search (FTS5)
        # Create FTS5 virtual table for external content
        # We index 'content' and 'file_path' for keyword search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
                content,
                file_path,
                project_name UNINDEXED,
                chunk_id UNINDEXED,
                content='' -- External content (we store it in Chroma, but keep a copy for FTS if needed, or just index it)
            )
        """)

        # Actually, for "external content" FTS5 usually points to another table.
        # But since Chroma holds the content, we'll store a copy in a regular SQLite table
        # to act as the 'external content' for FTS5, or just use a standard FTS5 table if space permits.
        # Given the "Senior Developer" mindset, let's use a content table for better FTS5 performance and management.

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunk_content (
                chunk_id TEXT PRIMARY KEY,
                file_path TEXT,
                project_name TEXT,
                content TEXT
            )
        """)

        # Re-create FTS5 linked to chunk_content
        conn.execute("DROP TABLE IF EXISTS chunk_fts")
        conn.execute("""
            CREATE VIRTUAL TABLE chunk_fts USING fts5(
                content,
                file_path,
                project_name UNINDEXED,
                chunk_id UNINDEXED,
                content='chunk_content',
                content_rowid='rowid'
            )
        """)

        # Triggers for automatic FTS5 synchronization
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS chunk_content_ai AFTER INSERT ON chunk_content BEGIN
                INSERT INTO chunk_fts(rowid, content, file_path) VALUES (new.rowid, new.content, new.file_path);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS chunk_content_ad AFTER DELETE ON chunk_content BEGIN
                INSERT INTO chunk_fts(chunk_fts, rowid, content, file_path) VALUES('delete', old.rowid, old.content, old.file_path);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS chunk_content_au AFTER UPDATE ON chunk_content BEGIN
                INSERT INTO chunk_fts(chunk_fts, rowid, content, file_path) VALUES('delete', old.rowid, old.content, old.file_path);
                INSERT INTO chunk_fts(rowid, content, file_path) VALUES (new.rowid, new.content, new.file_path);
            END
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

                        # Priority 1: Hybrid Search (FTS5)
                        # Sync chunk_content for FTS5
                        # First, clear existing chunks for this file to avoid duplicates on re-index
                        self._writer_db_conn.execute("DELETE FROM chunk_content WHERE file_path = ?", (batch.file_path,))

                        # Prepare batch for SQLite insertion
                        # chunk_id, file_path, project_name, content
                        sqlite_batch = []
                        for i, cid in enumerate(batch.ids):
                            project_name = batch.metadatas[i].get("project_name", "unknown")
                            sqlite_batch.append((cid, batch.file_path, project_name, batch.docs[i]))

                        self._writer_db_conn.executemany(
                            "INSERT INTO chunk_content (chunk_id, file_path, project_name, content) VALUES (?, ?, ?, ?)",
                            sqlite_batch
                        )

                        # 3. Update File State only after DB success
                        self._update_file_state(self._writer_db_conn, batch.file_path, batch.stats_str)

                        self._writer_db_conn.commit()
                except Exception as e:
                    logger.error("Consumer failed to write batch for %s: %s", batch.file_path, e)
                    self._writer_db_conn.rollback()
                finally:
                    self.work_queue.task_done()

            except Exception as e:
                logger.error("Unexpected error in Indexer Consumer loop: %s", e)

        logger.info("Indexer Consumer thread stopped.")

    def _wait_for_queue(self):
        """Monitor the consumer thread while waiting for progress (Deadlock Prevention)."""
        while self.work_queue.unfinished_tasks > 0:
            # If the consumer died, join() would hang forever
            if self._consumer_thread is None or not self._consumer_thread.is_alive():
                logger.error("Consumer thread died while work remains in queue. Aborting join.")
                break
            time.sleep(0.1)

    def _start_consumer(self):
        """Start the consumer thread if not running."""
        if self._consumer_thread is None or not self._consumer_thread.is_alive():
            self._consumer_thread = threading.Thread(target=self._consumer_loop, daemon=True)
            self._consumer_thread.start()

    def _stop_consumer(self):
        """Stop the consumer thread by sending a sentinel (Graceful Shutdown Hardening)."""
        if self._consumer_thread and self._consumer_thread.is_alive():
            logger.debug("Sending STOP sentinel to indexer consumer...")
            
            # 1. Wait for existing work to complete naturally (Worker Hardening)
            self._wait_for_queue()
            
            # 2. Send sentinel
            self.work_queue.put(None)
            
            # 3. Wait for thread to exit with timeout
            try:
                self._consumer_thread.join(timeout=5.0)
                if self._consumer_thread.is_alive():
                    logger.warning("Indexer consumer thread did not exit in time. Clearing queue to unblock.")
                    # Force clear the queue if join is taking too long
                    while not self.work_queue.empty():
                        try:
                            self.work_queue.get_nowait()
                            self.work_queue.task_done()
                        except queue.Empty:
                            break
                    # Final attempt to join
                    self._consumer_thread.join(timeout=2.0)
            except Exception as e:
                logger.error("Error during indexer consumer join: %s", e)
            finally:
                self._consumer_thread = None
    def rebuild_database(self) -> str:
        """
        [DEPRECATED] Use core.dependencies.factory_reset() instead.
        This local method is kept for legacy compatibility but delegates to the global orchestrator.
        """
        logger.warning("Local rebuild_database called. Delegating to global factory_reset...")
        from core.dependencies import factory_reset
        return factory_reset()

    def _delete_file_state(self, conn: sqlite3.Connection, file_path: str):
        """Remove a file from the state DB and chunk content (Pillar I/Priority 1)."""
        conn.execute("DELETE FROM file_state WHERE file_path = ?", (file_path,))
        conn.execute("DELETE FROM chunk_content WHERE file_path = ?", (file_path,))
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

        # Wait for all batches to be written to DB by the consumer thread
        self._wait_for_queue()

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

        # Use AST-enhanced splitting if available
        if hasattr(splitter, "split_with_metadata"):
            chunks_data = splitter.split_with_metadata(content)
        else:
            # Fallback to generic splitting
            chunks = splitter.split_text(content)
            chunks_data = [{"text": c, "metadata": {}} for c in chunks]

        if not chunks_data:
            return 0, 0

        prepared_ids = []
        prepared_metas = []
        prepared_docs = []

        current_char_idx = 0
        total_tokens_file = 0

        for i, chunk_item in enumerate(chunks_data):
            chunk = chunk_item["text"]
            ast_meta = chunk_item.get("metadata", {})

            start_idx = content.find(chunk, current_char_idx)
            if start_idx == -1:
                start_idx = current_char_idx

            start_line = content.count("\n", 0, start_idx) + 1

            meta = {
                "file_path": file_path,
                "extension": ext,
                "start_line": start_line,
                "project_name": project_name,
                "model": getattr(self.collection, "name", "unknown")
            }
            # Merge AST-enhanced metadata (imports, class hierarchy)
            if ast_meta.get("imports"):
                meta["imports"] = ast_meta["imports"]
            if ast_meta.get("class_hierarchy"):
                # Chroma metadata doesn't support lists, so we join it
                meta["class_hierarchy"] = " > ".join(ast_meta["class_hierarchy"])

            prepared_metas.append(meta)
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

        # Sync update: wait for completion
        self._wait_for_queue()

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
            file_paths = list({m["file_path"] for m in metadatas if m and m.get("file_path")})

            # Batch delete chunks from vector DB
            for i in range(0, len(ids_to_delete), 10000):
                self.collection.delete(ids=ids_to_delete[i:i+10000])

            # Batch remove from SQLite state
            self._batch_delete_file_state(self._writer_db_conn, file_paths)

        return {"deleted_chunks": len(ids_to_delete), "deleted_files": len(file_paths)}

    def _batch_delete_file_state(self, conn: sqlite3.Connection, file_paths: List[str]):
        """Remove multiple files from the state DB in batches (optimized)."""
        if not file_paths:
            return

        batch_size = 500
        for i in range(0, len(file_paths), batch_size):
            batch = file_paths[i:i+batch_size]
            placeholders = ",".join(["?"] * len(batch))
            conn.execute(f"DELETE FROM file_state WHERE file_path IN ({placeholders})", batch)
            conn.execute(f"DELETE FROM chunk_content WHERE file_path IN ({placeholders})", batch)
            conn.commit()

    def _delete_project_root(self, conn: sqlite3.Connection, folder_path: str):
        """Remove a project root from the state DB."""
        conn.execute("DELETE FROM project_roots WHERE folder_path = ?", (folder_path,))
        conn.commit()

    def prune_stale_files(self) -> dict:
        """Scan index for files and roots that no longer exist on disk and remove them (optimized)."""
        logger.info("Starting maintenance: pruning stale files and roots.")

        # 1. Prune Stale Files
        all_stats = self._get_all_file_stats()
        stale_file_paths = []
        for file_path in all_stats.keys():
            if not os.path.exists(file_path):
                stale_file_paths.append(file_path)

        if stale_file_paths:
            logger.info("Pruning %d non-existent files.", len(stale_file_paths))
            with self._db_lock:
                # 1.1 Delete from Vector DB (Chroma)
                # Chroma doesn't have a direct 'where file_path IN [...]', so we use metadata filter
                # or just delete file by file if the batch is small, but for production,
                # we query IDs first then delete.
                for i in range(0, len(stale_file_paths), 100):
                    batch = stale_file_paths[i:i+100]
                    results = self.collection.get(where={"file_path": {"$in": batch}}, include=[])
                    if results and results.get("ids"):
                        self.collection.delete(ids=results["ids"])

                # 1.2 Delete from SQLite state
                self._batch_delete_file_state(self._writer_db_conn, stale_file_paths)

        # 2. Prune Stale Project Roots
        indexed_roots = self.get_indexed_roots()
        pruned_roots = 0
        with self._db_lock:
            for root in indexed_roots:
                if not os.path.exists(root):
                    logger.info("Pruning non-existent project root: %s", root)
                    self._delete_project_root(self._writer_db_conn, root)
                    pruned_roots += 1

        # 3. Reclaim Disk Space (Production Hardening)
        pruned_count = len(stale_file_paths) + pruned_roots
        if pruned_count > 0:
            logger.info("Executed maintenance: pruned %d items. Vacuuming SQLite database...", pruned_count)
            try:
                with self._db_lock:
                    self._writer_db_conn.execute("VACUUM")
            except Exception as e:
                logger.error("Failed to vacuum database: %s", e)

        return {
            "pruned_files": len(stale_file_paths),
            "pruned_roots": pruned_roots
        }
