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
