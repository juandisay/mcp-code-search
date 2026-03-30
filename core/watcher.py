import logging
import os
import queue
import threading
import time
from typing import Dict, Tuple

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from core.indexer import CodeIndexer

logger = logging.getLogger(__name__)

class IndexerEventHandler(FileSystemEventHandler):
    """Handles watchdog events and pushes them to a processing queue."""

    def __init__(self, event_queue: queue.Queue, indexer: CodeIndexer):
        super().__init__()
        self.queue = event_queue
        self.indexer = indexer

    def _should_process(self, file_path: str) -> bool:
        """Aggressive pre-queue filtering to avoid memory bloat from unwanted events."""
        # 1. Quick check for common excluded directories (no-op for mass events in node_modules, etc.)
        normalized_path = file_path.replace(os.sep, "/")
        for excluded in self.indexer.excluded_dirs:
            # Match directories properly (e.g. /node_modules/ or ending with /node_modules)
            if f"/{excluded}/" in normalized_path or normalized_path.endswith(f"/{excluded}"):
                return False

        # 2. Check supported extensions
        _, ext = os.path.splitext(file_path)
        if ext not in self.indexer.supported_extensions:
            return False

        return True

    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self.queue.put(("created", event.src_path))

    def on_modified(self, event):
        # some editors create/delete temp files, focus on modified
        if not event.is_directory and self._should_process(event.src_path):
            self.queue.put(("modified", event.src_path))

    def on_deleted(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self.queue.put(("deleted", event.src_path))

class BatchEventProcessor(threading.Thread):
    """Consumes file events from a queue, debounces them, and triggers re-indexing."""

    def __init__(
        self,
        event_queue: queue.Queue,
        indexer: CodeIndexer,
        project_name: str,
        debounce_seconds: float = 2.0
    ):
        super().__init__(name=f"WatcherProcessor-{project_name}", daemon=True)
        self.queue = event_queue
        self.indexer = indexer
        self.project_name = project_name
        self.debounce_seconds = debounce_seconds
        
        self._stop_event = threading.Event()
        # file_path -> (last_event_type, last_seen_time)
        self._pending_updates: Dict[str, Tuple[str, float]] = {}

    def run(self):
        logger.info("BatchEventProcessor thread started for '%s'.", self.project_name)
        while not self._stop_event.is_set():
            try:
                # 1. Drain the queue into our pending map (Deduplication)
                q_depth = self.queue.qsize()
                if q_depth > 50:
                    logger.warning("Watcher: High queue depth detected: %d events", q_depth)

                while True:
                    try:
                        item = self.queue.get_nowait()
                        if item is None:
                            logger.debug("BatchEventProcessor: Received sentinel (None). Exiting loop.")
                            self._stop_event.set()
                            self.queue.task_done()
                            break

                        etype, path = item
                        self._pending_updates[path] = (etype, time.time())
                        self.queue.task_done()
                    except queue.Empty:
                        break

                # 2. Identify files that have "settled" (quiescence period)
                now = time.time()
                paths_to_flush = []
                for path, (etype, last_seen) in list(self._pending_updates.items()):
                    if now - last_seen >= self.debounce_seconds:
                        paths_to_flush.append(path)

                # 3. Process the batch
                if paths_to_flush:
                    logger.debug("Flushing batch of %d file updates from watcher.", len(paths_to_flush))
                    for path in paths_to_flush:
                        etype, _ = self._pending_updates.pop(path)
                        try:
                            if etype == "deleted":
                                logger.info("Watcher: Sync deleting %s", path)
                                self.indexer.delete_file(path)
                            else:
                                logger.info("Watcher: Sync updating %s", path)
                                self.indexer.update_file(path, self.project_name)
                        except Exception as e:
                            logger.error("Watcher: Error indexing %s: %s", path, e)

                # 4. Sleep briefly to prevent tight loop CPU usage
                # We use a 100ms sleep for good responsiveness
                time.sleep(0.1)

            except Exception as e:
                logger.error("Critical error in BatchEventProcessor: %s", e)
                time.sleep(1.0) # Avoid rapid retry on persistent errors

        logger.info("BatchEventProcessor thread for '%s' stopped.", self.project_name)

    def stop(self):
        """Signal the thread to stop via sentinel (Poison Pill)."""
        logger.debug("BatchEventProcessor: Sending sentinel to stop thread.")
        self.queue.put(None)
        self._stop_event.set()

class ProjectWatcher:
    """Manages the watchdog observer and batch processor for a project folder."""

    def __init__(self, indexer: CodeIndexer):
        self.indexer = indexer
        self.observer = None
        self.processor = None
        self.watched_folder = None
        self.event_queue = queue.Queue(maxsize=2000)

    def start(self, folder_path: str):
        """Start watching a folder with batch processing."""
        folder_path = os.path.abspath(folder_path)

        if self.observer:
            if self.watched_folder == folder_path:
                logger.debug("Watcher already running for %s", folder_path)
                return
            self.stop()

        if not os.path.isdir(folder_path):
            logger.error("Cannot start watcher: folder does not exist: %s", folder_path)
            return

        self.watched_folder = folder_path
        project_name = os.path.basename(folder_path)

        # Clear queue for new project
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
                self.event_queue.task_done()
            except queue.Empty:
                break

        # 1. Start Batch Processor
        self.processor = BatchEventProcessor(self.event_queue, self.indexer, project_name)
        self.processor.start()

        # 2. Start Watchdog Observer
        event_handler = IndexerEventHandler(self.event_queue, self.indexer)
        self.observer = Observer()
        self.observer.schedule(event_handler, folder_path, recursive=True)
        self.observer.start()

        logger.info("Started memory-efficient watcher for project '%s' at %s", project_name, folder_path)

    def stop(self):
        """Cleanly stop both the observer and the batch processor."""
        if self.observer:
            logger.info("Stopping watchdog observer for %s", self.watched_folder)
            self.observer.stop()
            self.observer.join()
            self.observer = None

        if self.processor:
            logger.info("Stopping batch processor for %s", self.watched_folder)
            self.processor.stop()
            self.processor.join()
            self.processor = None

        self.watched_folder = None
