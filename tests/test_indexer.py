"""Tests for core.indexer module."""
from core.indexer import CodeIndexer, EXTENSION_TO_LANGUAGE


class TestCodeIndexer:
    """Tests for the CodeIndexer class."""

    def test_init_defaults(self):
        """Indexer initialises with default values."""
        indexer = CodeIndexer()
        assert indexer.chunk_size == 1000
        assert indexer.chunk_overlap == 200
        assert indexer.batch_size == 100
        assert indexer.collection is not None

    def test_supported_extensions_includes_py(self):
        """Python extension is always supported."""
        indexer = CodeIndexer()
        assert ".py" in indexer.supported_extensions

    def test_excluded_dirs(self):
        """Common noise directories are excluded."""
        indexer = CodeIndexer()
        for d in (
            "node_modules", ".git",
            "venv", "__pycache__",
        ):
            assert d in indexer.excluded_dirs

    def test_index_project_folder(self, tmp_path):
        """Indexing a folder with .py files works."""
        sample = tmp_path / "hello.py"
        sample.write_text(
            "def hello():\n"
            "    return 'world'\n"
        )
        indexer = CodeIndexer()
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["files_processed"] > 0
        assert result["chunks_upserted"] > 0

    def test_index_skips_empty_files(self, tmp_path):
        """Empty files produce zero chunks."""
        empty = tmp_path / "empty.py"
        empty.write_text("")
        indexer = CodeIndexer()
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["chunks_upserted"] == 0

    def test_index_skips_excluded_dirs(self, tmp_path):
        """Files in excluded dirs are not indexed."""
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()
        hidden = venv_dir / "hidden.py"
        hidden.write_text("x = 1\n")
        indexer = CodeIndexer()
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["files_processed"] == 0

    def test_hash_cache_skips_unchanged(self, tmp_path):
        """Re-indexing unchanged files is skipped."""
        sample = tmp_path / "stable.py"
        sample.write_text("x = 42\n")
        indexer = CodeIndexer()
        indexer.index_project_folder(str(tmp_path))
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["files_skipped"] > 0

    def test_list_projects(self, tmp_path):
        """list_projects returns project name."""
        sample = tmp_path / "app.py"
        sample.write_text("print('hi')\n")
        indexer = CodeIndexer()
        indexer.index_project_folder(str(tmp_path))
        projects = indexer.list_projects()
        assert tmp_path.name in projects

    def test_extension_to_language_map(self):
        """Language map covers core extensions."""
        for ext in (".py", ".js", ".ts", ".go", ".java"):
            assert ext in EXTENSION_TO_LANGUAGE

    def test_custom_chunk_params(self):
        """Indexer respects custom chunk params."""
        indexer = CodeIndexer(
            chunk_size=500, chunk_overlap=50
        )
        assert indexer.chunk_size == 500
        assert indexer.chunk_overlap == 50
