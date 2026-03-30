import logging
import os
import shutil
import threading

import chromadb

from config import config

# Note: We don't call setup_logging here because main.py will do it
# to ensure the correct mcp_mode is set first.
logger = logging.getLogger(__name__)

# Singletons
_indexer = None
_searcher = None
_watcher = None

# Locks
_indexer_lock = threading.Lock()
_searcher_lock = threading.Lock()
_watcher_lock = threading.Lock()


def get_indexer():
    """Retrieve or initialize the CodeIndexer singleton (Thread-Safe)."""
    global _indexer
    if _indexer is None:
        with _indexer_lock:
            if _indexer is None:
                from core.indexer import CodeIndexer
                logger.info("Initializing CodeIndexer singleton...")
                _indexer = CodeIndexer(app_config=config)
    return _indexer


def get_searcher():
    """Retrieve or initialize the CodeSearcher singleton (Thread-Safe)."""
    global _searcher
    if _searcher is None:
        with _searcher_lock:
            if _searcher is None:
                from core.searcher import CodeSearcher
                logger.info("Initializing CodeSearcher singleton...")
                _searcher = CodeSearcher(app_config=config)
    return _searcher


def get_watcher():
    """Retrieve or initialize the ProjectWatcher singleton (Thread-Safe)."""
    global _watcher
    if _watcher is None:
        with _watcher_lock:
            if _watcher is None:
                from core.watcher import ProjectWatcher
                logger.info("Initializing ProjectWatcher singleton...")
                _watcher = ProjectWatcher(get_indexer())
    return _watcher


def shutdown_dependencies():
    """Gracefully shutdown all singletons."""
    global _watcher, _indexer, _searcher
    if _watcher:
        logger.info("Stopping ProjectWatcher...")
        _watcher.stop()
    if _indexer:
        logger.info("Shutting down CodeIndexer...")
        _indexer.shutdown()
    if _searcher:
        logger.info("Shutting down CodeSearcher...")
        _searcher.shutdown()


def factory_reset() -> str:
    """Global wipe and re-initialization (Pillar III HARDENING)."""
    global _indexer, _searcher, _watcher
    logger.warning("FACTORY RESET: Rebuilding all database services from scratch.")

    with _indexer_lock, _searcher_lock, _watcher_lock:
        # 1. Graceful Shutdown of singleton services
        try:
            if _watcher:
                _watcher.stop()
            if _indexer:
                _indexer.shutdown()
            if _searcher:
                _searcher.shutdown()
        except Exception as e:
            logger.error("Error during service shutdown: %s", e)

        # 2. Critical: Clear ChromaDB global cache to release file handles
        try:
            # Keep imports local for these edge-case recovery tools
            # This is essential for preventing 'malformed' errors after deletion
            chromadb.api.client.SharedSystemClient.clear_system_cache()
            logger.info("ChromaDB system cache cleared.")
        except Exception as e:
            logger.warning("Could not clear ChromaDB cache: %s", e)

        # 3. Safely wipe the physical data directory
        data_path = config.CHROMA_DATA_PATH
        if os.path.exists(data_path):
            try:
                # Give the OS a tiny moment to release handles if needed
                import time
                time.sleep(0.5)
                shutil.rmtree(data_path, ignore_errors=True)
                logger.info("Database physical storage wiped: %s", data_path)
            except Exception as e:
                logger.error("Failed to wipe data directory: %s", e)

        # 4. Reset singleton pointers to force fresh initialization
        _indexer = None
        _searcher = None
        _watcher = None

        # 5. Re-bootstrap essential singletons
        try:
            get_indexer()
            get_searcher()
            logger.info("Services re-initialized successfully.")
        except Exception as e:
            logger.error("Failed to re-initialize services after reset: %s", e)
            return f"ERROR: Reset failed during re-initialization: {e}"

    return "SUCCESS: Code-Search database has been completely rebuilt from scratch."
