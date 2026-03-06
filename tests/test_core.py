"""Tests for the old test_core integration test."""
import os

from core.indexer import CodeIndexer
from core.searcher import CodeSearcher


def test_core_engine():
    """Integration: index core/ and search for code."""
    indexer = CodeIndexer()

    folder_to_index = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..", "core",
        )
    )

    indexer.index_project_folder(folder_to_index)

    count = indexer.collection.count()
    assert count > 0, "No documents were indexed."

    searcher = CodeSearcher()
    results = searcher.search(
        "ChromaDB client", n_results=2
    )

    assert len(results) > 0, "No search results."
