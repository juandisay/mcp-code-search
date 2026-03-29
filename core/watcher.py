import logging
import os
from threading import Timer

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from core.indexer import CodeIndexer

logger = logging.getLogger(__name__)

class IndexerEventHandler(FileSystemEventHandler):
    """Handles watchdog events and translates them to CodeIndexer updates."""

    def __init__(self, indexer: CodeIndexer, project_name: str, debounce_seconds: float = 2.0):
        super().__init__()
        self.indexer = indexer
        self.project_name = project_name
        self.debounce_seconds = debounce_seconds

        # Track pending updates: file_path -> Timer mapping
        self._timers = {}

    def _debounce_update(self, event_type: str, file_path: str):
        """Schedule an update after a brief delay to avoid rapid duplicate events."""
        # Cancel existing timer for this file if present
        if file_path in self._timers:
            self._timers[file_path].cancel()

        def execute_update():
            # Clean up timer reference
            self._timers.pop(file_path, None)

            try:
                if event_type == "deleted":
                    logger.info("Watcher: File deleted, removing from index: %s", file_path)
                    self.indexer.delete_file(file_path)
                elif event_type in ["created", "modified"]:
                    logger.info("Watcher: File %s, updating index: %s", event_type, file_path)
                    self.indexer.update_file(file_path, self.project_name)
            except Exception as e:
                logger.error("Watcher error handling %s for %s: %s", event_type, file_path, e)

        # Set new timer
        timer = Timer(self.debounce_seconds, execute_update)
        self._timers[file_path] = timer
        timer.start()

    def _should_process(self, file_path: str) -> bool:
        """Check if the file is one we should process based on indexer rules."""
        # Ignore excluded directories (like .git, node_modules)
        for excluded in self.indexer.excluded_dirs:
            # Match directories properly (e.g. /node_modules/ or ending with /node_modules)
            if f"/{excluded}/" in file_path.replace(os.sep, "/") or file_path.endswith(excluded):
                return False

        # Check supported extensions based on what the indexer allows
        _, ext = os.path.splitext(file_path)
        if ext not in self.indexer.supported_extensions:
            return False

        return True

    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self._debounce_update("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self._debounce_update("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self._debounce_update("deleted", event.src_path)

class ProjectWatcher:
    """Manages the watchdog observer for a specific project directory."""

    def __init__(self, indexer: CodeIndexer):
        self.indexer = indexer
        self.observer = None
        self.watched_folder = None

    def start(self, folder_path: str):
        """Start watching a folder for changes."""
        # Normalize path
        folder_path = os.path.abspath(folder_path)

        if self.observer:
            if self.watched_folder == folder_path:
                logger.info("Watcher already running for %s", folder_path)
                return
            self.stop()

        if not os.path.isdir(folder_path):
            logger.error("Cannot start watcher: folder does not exist: %s", folder_path)
            return

        self.watched_folder = folder_path
        project_name = os.path.basename(folder_path)

        event_handler = IndexerEventHandler(self.indexer, project_name)

        self.observer = Observer()
        self.observer.schedule(event_handler, folder_path, recursive=True)
        self.observer.start()
        logger.info("Started file watcher for project '%s' at %s", project_name, folder_path)

    def stop(self):
        """Stop tracking the current folder."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Stopped file watcher for %s", self.watched_folder)
            self.observer = None
            self.watched_folder = None
