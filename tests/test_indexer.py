from core.indexer import CodeIndexer, AST_SUPPORTED_EXTENSIONS


class TestCodeIndexer:
    """Tests for the CodeIndexer class."""

    def test_init_defaults(self, app_config):
        """Indexer initialises with default values."""
        indexer = CodeIndexer(app_config=app_config)
        assert indexer.chunk_size == 1000
        assert indexer.chunk_overlap == 200
        assert indexer.batch_size == 100
        assert indexer.collection is not None

    def test_supported_extensions_includes_py(self, app_config):
        """Python extension is always supported."""
        indexer = CodeIndexer(app_config=app_config)
        assert ".py" in indexer.supported_extensions

    def test_excluded_dirs(self, app_config):
        """Common noise directories are excluded."""
        indexer = CodeIndexer(app_config=app_config)
        for d in (
            "node_modules", ".git",
            "venv", "__pycache__",
        ):
            assert d in indexer.excluded_dirs

    def test_index_project_folder(self, tmp_path, app_config):
        """Indexing a folder with .py files works."""
        # Isolation: Use a temporary ChromaDB path for this test
        app_config.CHROMA_DATA_PATH = str(tmp_path / "chroma_db_indexer")
        
        sample = tmp_path / "hello.py"
        sample.write_text(
            "def hello():\n"
            "    return 'world'\n"
        )
        indexer = CodeIndexer(app_config=app_config)
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["files_processed"] > 0
        assert result["chunks_upserted"] > 0

    def test_index_skips_empty_files(self, tmp_path, app_config):
        """Empty files produce zero chunks."""
        # Isolation
        app_config.CHROMA_DATA_PATH = str(tmp_path / "chroma_db_empty")
        
        empty = tmp_path / "empty.py"
        empty.write_text("")
        indexer = CodeIndexer(app_config=app_config)
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["chunks_upserted"] == 0

    def test_index_skips_excluded_dirs(self, tmp_path, app_config):
        """Files in excluded dirs are not indexed."""
        # Isolation
        app_config.CHROMA_DATA_PATH = str(tmp_path / "chroma_db_excluded")
        
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()
        hidden = venv_dir / "hidden.py"
        hidden.write_text("x = 1\n")
        indexer = CodeIndexer(app_config=app_config)
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["files_processed"] == 0

    def test_hash_cache_skips_unchanged(self, tmp_path, app_config):
        """Re-indexing unchanged files is skipped."""
        # Isolation
        app_config.CHROMA_DATA_PATH = str(tmp_path / "chroma_db_cache")
        
        sample = tmp_path / "stable.py"
        sample.write_text("x = 42\n")
        indexer = CodeIndexer(app_config=app_config)
        indexer.index_project_folder(str(tmp_path))
        result = indexer.index_project_folder(
            str(tmp_path)
        )
        assert result["files_skipped"] > 0

    def test_list_projects(self, tmp_path, app_config):
        """list_projects returns project name."""
        # Isolation
        app_config.CHROMA_DATA_PATH = str(tmp_path / "chroma_db_list")
        
        sample = tmp_path / "app.py"
        sample.write_text("print('hi')\n")
        indexer = CodeIndexer(app_config=app_config)
        indexer.index_project_folder(str(tmp_path))
        projects = indexer.list_projects()
        assert tmp_path.name in projects

    def test_extension_to_language_map(self):
        """Language map covers core extensions."""
        for ext in (".py", ".js", ".ts", ".go", ".java"):
            assert ext in AST_SUPPORTED_EXTENSIONS

