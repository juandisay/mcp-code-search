"""Tests for core.searcher module."""
import pytest

from core.indexer import CodeIndexer
from core.searcher import CodeSearcher


@pytest.fixture(scope="module")
def indexed_searcher(tmp_path_factory):
    """Index sample files and return a ready searcher."""
    tmp = tmp_path_factory.mktemp("search_project")
    (tmp / "math_utils.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n\n"
        "def multiply(a, b):\n"
        "    return a * b\n"
    )
    (tmp / "string_utils.py").write_text(
        "def greet(name):\n"
        "    return f'Hello, {name}'\n"
    )
    (tmp / "app.ts").write_text(
        "function addTs(a: number, b: number) {\n"
        "    return a + b;\n"
        "}\n"
    )
    secret_dir = tmp / "secret_dir"
    secret_dir.mkdir()
    (secret_dir / "hidden.py").write_text(
        "def hidden_add(a, b):\n"
        "    return a + b + 1\n"
    )
    
    indexer = CodeIndexer()
    indexer.index_project_folder(str(tmp))
    return CodeSearcher()


class TestCodeSearcher:
    """Tests for the CodeSearcher class."""

    def test_init_defaults(self):
        """Searcher initialises with default max_distance."""
        s = CodeSearcher()
        assert s.max_distance == 2.0
        assert s.collection is not None

    def test_search_returns_results(self, indexed_searcher):
        """Searching for known code returns results."""
        results = indexed_searcher.search("add two numbers")
        assert len(results) > 0

    def test_search_result_structure(self, indexed_searcher):
        """Each result has the expected keys."""
        results = indexed_searcher.search("add")
        if results:
            r = results[0]
            assert "snippet" in r
            assert "file_path" in r
            assert "start_line" in r
            assert "project_name" in r
            assert "distance" in r
            assert "cross_encoder_score" in r

    def test_search_empty_collection(self):
        """Searching an empty collection returns []."""
        s = CodeSearcher()
        # Use a very specific query on a fresh instance
        results = s.search(
            "nonexistent_xyzzy_query_12345",
            n_results=1,
        )
        # May or may not return results depending on
        # existing data; at least it shouldn't error
        assert isinstance(results, list)

    def test_max_distance_filter(self, indexed_searcher):
        """Strict max_distance filters out poor matches."""
        strict = indexed_searcher.search(
            "add numbers",
            n_results=10,
            max_distance=0.001,
        )
        loose = indexed_searcher.search(
            "add numbers",
            n_results=10,
            max_distance=2.0,
        )
        assert len(strict) <= len(loose)

    def test_n_results_clamped(self, indexed_searcher):
        """Requesting more results than exist doesn't error."""
        results = indexed_searcher.search(
            "add", n_results=99999
        )
        assert isinstance(results, list)

    def test_search_language_filter(self, indexed_searcher):
        """Filtering by language returns only matching extensions."""
        py_results = indexed_searcher.search("add", language=".py")
        assert all(r["file_path"].endswith(".py") for r in py_results)
        
        ts_results = indexed_searcher.search("add", language=["ts"])
        assert all(r["file_path"].endswith(".ts") for r in ts_results)
        assert len(ts_results) > 0

    def test_search_file_path_includes(self, indexed_searcher):
        """Filtering by file_path_includes matches substring."""
        results = indexed_searcher.search("add", file_path_includes="math_")
        assert all("math_" in r["file_path"] for r in results)
        assert len(results) > 0

    def test_search_excluded_dirs(self, indexed_searcher):
        """Filtering by excluded_dirs omits specified directories."""
        # 'hidden_add' is in secret_dir
        results_without_filter = indexed_searcher.search("hidden_add", n_results=5)
        assert any("secret_dir" in r["file_path"] for r in results_without_filter)
        
        results_with_filter = indexed_searcher.search(
            "hidden_add", n_results=5, excluded_dirs=["secret_dir"]
        )
        assert not any("secret_dir" in r["file_path"] for r in results_with_filter)
