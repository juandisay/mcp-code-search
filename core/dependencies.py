import threading
import logging
import sys
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
    global _watcher, _indexer
    if _watcher:
        logger.info("Stopping ProjectWatcher...")
        _watcher.stop()
    if _indexer:
        logger.info("Shutting down CodeIndexer...")
        _indexer.shutdown()
