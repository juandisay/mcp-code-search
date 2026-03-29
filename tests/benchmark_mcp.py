import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import config
from core.indexer import CodeIndexer
from core.searcher import CodeSearcher


def benchmark():
    print("--- MCP Performance Benchmark ---")

    # Initialise searcher
    start_init = time.time()
    searcher = CodeSearcher()
    print(f"Searcher Init: {time.time() - start_init:.4f}s")

    query = "function to upload file to s3"

    # 1. Search with Re-ranking (Default)
    config.USE_RERANKER = True
    config.RE_RANK_LIMIT = 20
    start = time.time()
    results = searcher.search(query, n_results=3, re_rank=True)
    print(f"Search with Re-rank (Limit 20): {time.time() - start:.4f}s (Results: {len(results)})")

    # 2. Search WITHOUT Re-ranking
    start = time.time()
    results = searcher.search(query, n_results=3, re_rank=False)
    print(f"Search WITHOUT Re-rank: {time.time() - start:.4f}s (Results: {len(results)})")

    # 3. Indexing speed test
    indexer = CodeIndexer()
    test_folder = os.getcwd() # Index itself
    print(f"\nIndexing folder: {test_folder}")

    # First run (should use fast mtime check if already indexed)
    start = time.time()
    summary = indexer.index_project_folder(test_folder)
    print(f"Incremental Index (mtime check): {time.time() - start:.4f}s")
    print(f"Summary: {summary}")

if __name__ == "__main__":
    benchmark()
