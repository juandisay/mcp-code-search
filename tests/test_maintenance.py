import os
import shutil
import pytest
from core.indexer import CodeIndexer

class TestMaintenance:
    """Tests for the Automated Maintenance (Garbage Collection) logic."""

    def test_prune_stale_files(self, tmp_path, app_config):
        """Pruning removes files that no longer exist on disk."""
        # Isolation: Use a temporary ChromaDB path for this test
        app_config.CHROMA_DATA_PATH = str(tmp_path / "chroma_db_maintenance")

        # 1. Create and index a file
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        file_path = project_dir / "hello.py"
        file_path.write_text("def hello(): return 'world'")
        
        indexer = CodeIndexer(app_config=app_config)
        indexer.index_project_folder(str(project_dir))
        
        # Verify it's indexed
        assert indexer.collection.count() > 0
        all_stats = indexer._get_all_file_stats()
        assert str(file_path) in all_stats

        # 2. Delete the file from disk
        os.remove(file_path)
        
        # 3. Run maintenance prune
        summary = indexer.prune_stale_files()
        
        # 4. Verify it's removed from index
        assert summary["pruned_files"] == 1
        assert indexer.collection.count() == 0
        all_stats = indexer._get_all_file_stats()
        assert str(file_path) not in all_stats

    def test_prune_stale_roots(self, tmp_path, app_config):
        """Pruning removes project roots that no longer exist on disk."""
        # Isolation
        app_config.CHROMA_DATA_PATH = str(tmp_path / "chroma_db_roots")

        # 1. Index a folder
        project_dir = tmp_path / "gone_project"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("print('bye')")
        
        indexer = CodeIndexer(app_config=app_config)
        indexer.index_project_folder(str(project_dir))
        
        # Verify root is recorded
        roots = indexer.get_indexed_roots()
        assert str(project_dir) in roots

        # 2. Delete the folder from disk
        shutil.rmtree(project_dir)
        
        # 3. Run maintenance prune
        summary = indexer.prune_stale_files()
        
        # 4. Verify root is removed
        assert summary["pruned_roots"] == 1
        roots = indexer.get_indexed_roots()
        assert str(project_dir) not in roots
