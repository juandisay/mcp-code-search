"""Semantic search queries against ChromaDB."""
import logging
import sys
import contextlib
import concurrent.futures
from typing import Any, Dict, List, Optional, Union

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import CrossEncoder
from config import config

logger = logging.getLogger(__name__)

@contextlib.contextmanager
def redirect_stdout_to_stderr():
    """Redirect all stdout to stderr temporarily."""
    original_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = original_stdout


class CodeSearcher:
    """Query ChromaDB for code snippets."""

    def __init__(
        self, max_distance: float = config.MAX_DISTANCE
    ):
        """Initialise the searcher.

        Args:
            max_distance: Default cosine distance cap.
        """
        self.chroma_client = chromadb.PersistentClient(
            path=config.CHROMA_DATA_PATH
        )
        self.embedding_fn = (
            embedding_functions.DefaultEmbeddingFunction()
        )
        self.collection = (
            self.chroma_client.get_or_create_collection(
                name="code_snippets",
                embedding_function=self.embedding_fn,
            )
        )
        self.max_distance = max_distance
        
        # Initialize Cross-Encoder for two-stage reranking
        logger.info("Loading CrossEncoder model: %s", config.CROSS_ENCODER_MODEL)
        with redirect_stdout_to_stderr():
            self.cross_encoder = CrossEncoder(config.CROSS_ENCODER_MODEL)

    def search(
        self,
        query: str,
        n_results: int = 3,
        project_name: Optional[
            Union[str, List[str]]
        ] = None,
        max_distance: Optional[float] = None,
        language: Optional[Union[str, List[str]]] = None,
        file_path_includes: Optional[str] = None,
        excluded_dirs: Optional[Union[str, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB for relevant code snippets.

        Args:
            query: Natural language search query.
            n_results: Max number of results.
            project_name: Filter by project(s).
            max_distance: Override distance threshold.
            language: Filter by file extension(s).
            file_path_includes: Require a specific substring in file path.
            excluded_dirs: Exclude directories from search.
        """
        collection_count = self.collection.count()
        if collection_count == 0:
            return []
            
        # Stage 1: Fetch larger candidate pool
        initial_k = max(n_results, config.INITIAL_RETRIEVAL_COUNT)
        
        if language or file_path_includes or excluded_dirs:
            # Fetch more matches to offset post-retrieval filtering
            initial_k = min(initial_k * 5, collection_count)
        else:
            initial_k = min(initial_k, collection_count)

        # Sanity check: cap initial_k to prevent SQL variable limit errors (typically 999 or 32766)
        # We'll use a safe 5000 to be conservative and prevent huge query overhead.
        initial_k = max(1, min(initial_k, 5000))


        where_clause = None
        if project_name:
            if isinstance(project_name, list):
                where_clause = {
                    "project_name": {
                        "$in": project_name
                    }
                }
            else:
                where_clause = {
                    "project_name": project_name
                }

        results = self.collection.query(
            query_texts=[query],
            n_results=initial_k,
            where=where_clause,
            include=[
                "documents", "metadatas", "distances"
            ],
        )

        threshold = (
            max_distance
            if max_distance is not None
            else self.max_distance
        )

        formatted: List[Dict[str, Any]] = []
        docs_list = (results or {}).get("documents")
        if not docs_list or not docs_list[0]:
            return formatted

        docs = docs_list[0]
        metas = (
            results["metadatas"][0]
            if results.get("metadatas")
            else [{}] * len(docs)
        )
        distances = (
            results["distances"][0]
            if results.get("distances")
            else [None] * len(docs)
        )

        candidates: List[Dict[str, Any]] = []
        for doc, meta, dist in zip(
            docs, metas, distances
        ):
            if dist is not None and dist > threshold:
                continue
                
            file_path = meta.get("file_path", "")
            
            # Stage 1.5: Python-level Metadata Filtering
            if language:
                langs = language if isinstance(language, list) else [language]
                langs = [ext if ext.startswith('.') else f".{ext}" for ext in langs]
                if not any(file_path.endswith(ext) for ext in langs):
                    continue
                    
            if file_path_includes and file_path_includes not in file_path:
                continue
                
            if excluded_dirs:
                ex_dirs = excluded_dirs if isinstance(excluded_dirs, list) else [excluded_dirs]
                skip = False
                for ex_dir in ex_dirs:
                    ex_dir_clean = ex_dir.strip('/')
                    # Path boundary match so we don't accidentally exclude similar substrings
                    if f"/{ex_dir_clean}/" in f"/{file_path.strip('/')}/":
                        skip = True
                        break
                if skip:
                    continue

            candidates.append({
                "doc": doc,
                "meta": meta,
                "distance": dist
            })

        if not candidates:
            return []

        num_candidates = len(candidates)
        if num_candidates > config.RE_RANK_LIMIT:
            logger.info("Capping candidates from %d to %d for snippet loading and re-ranking", num_candidates, config.RE_RANK_LIMIT)
            candidates = candidates[:config.RE_RANK_LIMIT]
            
        def _load_snippet(candidate: dict) -> dict:
            meta = candidate["meta"]
            doc = candidate["doc"]
            
            snippet = doc
            if not snippet and meta and meta.get("chunk_file"):
                try:
                    with open(meta["chunk_file"], "r", encoding="utf-8") as f:
                        snippet = f.read()
                except Exception as e:
                    logger.warning("Could not read chunk file %s: %s", meta["chunk_file"], e)
                    snippet = "[Content could not be loaded]"
                    
            return {
                "snippet": snippet,
                "file_path": meta.get("file_path", ""),
                "start_line": meta.get("start_line", 0),
                "project_name": meta.get("project_name", ""),
                "distance": candidate["distance"],
            }

        # Load snippets in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, len(candidates))) as executor:
            formatted = list(executor.map(_load_snippet, candidates))
        
        cross_inp = [[query, item["snippet"]] for item in formatted]
        with redirect_stdout_to_stderr():
            cross_scores = self.cross_encoder.predict(cross_inp)

        for idx, score in enumerate(cross_scores):
            formatted[idx]["cross_encoder_score"] = float(score)

        # Sort by cross-encoder score descending
        formatted.sort(key=lambda x: x["cross_encoder_score"], reverse=True)

        # Return top N
        return formatted[:n_results]
