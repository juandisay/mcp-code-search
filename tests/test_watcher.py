import os
import time
from pathlib import Path

from core.indexer import CodeIndexer
from core.watcher import ProjectWatcher


def test_watcher_integration(tmp_path: Path):
    """Test that file creation and modification triggers the indexer."""
    test_project = tmp_path / "test_project"
    test_project.mkdir()

    # Mock the indexer's methods to track calls safely
    class MockIndexer(CodeIndexer):
        def __init__(self):
            self.excluded_dirs = set()
            self.supported_extensions = {".py", ".txt"}
            self.updated_files = []
            self.deleted_files = []

        def update_file(self, file_path, project_name):
            self.updated_files.append(file_path)

        def delete_file(self, file_path):
            self.deleted_files.append(file_path)

    mock_indexer = MockIndexer()
    watcher = ProjectWatcher(mock_indexer)
    watcher.start(str(test_project))

    # Speed up debounce for tests by monkeypatching the handler
    # Observer -> emitters -> watch -> handlers (set)
    for emitter in watcher.observer.emitters:
        for handler in watcher.observer._handlers[emitter.watch]:
            handler.debounce_seconds = 0.1

    # Create file
    test_file = test_project / "hello.py"
    with open(test_file, "w") as f:
        f.write("print('hello')")

    time.sleep(0.5)
    assert str(test_file) in mock_indexer.updated_files, "Creation did not trigger update_file"

    # Modify file
    with open(test_file, "a") as f:
        f.write("print('world')")

    time.sleep(0.5)
    assert sum(1 for f in mock_indexer.updated_files if f == str(test_file)) >= 2, "Modification did not trigger update_file"

    # Delete file
    os.remove(test_file)
    time.sleep(0.5)
    assert str(test_file) in mock_indexer.deleted_files, "Deletion did not trigger delete_file"

    watcher.stop()
