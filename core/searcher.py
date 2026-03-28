"""Semantic search queries against ChromaDB."""
import logging
import sys
import contextlib
import concurrent.futures
from typing import Any, Dict, List, Optional, Union

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import CrossEncoder

from core.db_utils import get_collection_name # Add this

logger = logging.getLogger(__name__)

# Detect hardware acceleration for Mac (MPS)
_DEVICE = "cpu"
if sys.platform == "darwin":
    try:
        import torch
        if torch.backends.mps.is_available():
            _DEVICE = "mps"
    except ImportError:
        pass


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
        self,
        app_config: Any,
        embedding_fn: Any = None,
    ):
        """Initialise the searcher.

        Args:
            app_config: Application configuration instance.
            embedding_fn: Optional custom embedding function.
        """
        self.config = app_config
        self.chroma_client = chromadb.PersistentClient(
            path=self.config.CHROMA_DATA_PATH
        )
        
        # Dependency Injection for Embedding Function
        self.embedding_fn = (
            embedding_fn or embedding_functions.DefaultEmbeddingFunction()
        )
        
        # Unified Collection Naming
        coll_name = get_collection_name(self.embedding_fn)
        
        self.collection = (
            self.chroma_client.get_or_create_collection(
                name=coll_name,
                embedding_function=self.embedding_fn,
            )
        )
        
        self.max_distance = self.config.MAX_DISTANCE
        self._cross_encoder = None

    @property
    def cross_encoder(self):
        """Lazy-load the Cross-Encoder model only when needed."""
        if self._cross_encoder is None:
            logger.info("Loading CrossEncoder model: %s on device: %s", self.config.CROSS_ENCODER_MODEL, _DEVICE)
            with redirect_stdout_to_stderr():
                self._cross_encoder = CrossEncoder(self.config.CROSS_ENCODER_MODEL, device=_DEVICE)
        return self._cross_encoder

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
        re_rank: Optional[bool] = None,
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
            re_rank: Whether to use cross-encoder reranking.
        """
        collection_count = self.collection.count()
        if collection_count == 0:
            return []
            
        should_re_rank = re_rank if re_rank is not None else self.config.USE_RERANKER
        
        # Stage 1: Fetch larger candidate pool if re-ranking, or exactly n_results if not
        if should_re_rank:
            initial_k = max(n_results, self.config.RE_RANK_LIMIT)
        else:
            initial_k = n_results
        
        # Adjust k if we have filters that might be applied in Python
        if file_path_includes or excluded_dirs:
             initial_k = min(initial_k * 5, collection_count, 5000)
        else:
             initial_k = min(initial_k, collection_count)

        initial_k = max(1, initial_k)

        # Build native where clause (Pillar II: push as much as possible to DB)
        where_conditions = []
        
        if project_name:
            if isinstance(project_name, list):
                if len(project_name) == 1:
                    where_conditions.append({"project_name": project_name[0]})
                else:
                    where_conditions.append({"project_name": {"$in": project_name}})
            else:
                where_conditions.append({"project_name": project_name})
        
        if language:
            langs = language if isinstance(language, list) else [language]
            langs = [ext if ext.startswith('.') else f".{ext}" for ext in langs]
            if len(langs) == 1:
                where_conditions.append({"extension": langs[0]})
            else:
                where_conditions.append({"extension": {"$in": langs}})

        # file_path_includes as native filter (experimental but recommended by Mahaguru)
        # We try to use $contains or $like if supported, else we fall back to Python filtering
        # Since we can't easily detect support without trial, we keep Python filter as safeguard.
        
        where_clause = None
        if len(where_conditions) == 1:
            where_clause = where_conditions[0]
        elif len(where_conditions) > 1:
            where_clause = {"$and": where_conditions}

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

        docs_list = (results or {}).get("documents")
        if not docs_list or not docs_list[0]:
            return []

        docs = docs_list[0]
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
        distances = results["distances"][0] if results.get("distances") else [None] * len(docs)

        candidates: List[Dict[str, Any]] = []
        for doc, meta, dist in zip(docs, metas, distances):
            if dist is not None and dist > threshold:
                continue
                
            file_path = meta.get("file_path", "")
            
            # Stage 1.5: Python-level Filtering (for things not in where clause)
            if file_path_includes and file_path_includes not in file_path:
                continue
                
            if excluded_dirs:
                ex_dirs = excluded_dirs if isinstance(excluded_dirs, list) else [excluded_dirs]
                if any(f"/{d.strip('/')}/" in f"/{file_path.strip('/')}/" for d in ex_dirs):
                    continue

            candidates.append({
                "doc": doc,
                "meta": meta,
                "distance": dist
            })

        if not candidates:
            return []

        # Load snippets in parallel
        def _load_snippet(candidate: dict) -> dict:
            meta = candidate["meta"]
            doc = candidate["doc"]
            snippet = doc
            if not snippet and meta and meta.get("chunk_file"):
                try:
                    with open(meta["chunk_file"], "r", encoding="utf-8") as f:
                        snippet = f.read()
                except Exception:
                    snippet = "[Content could not be loaded]"
            return {
                "snippet": snippet,
                "file_path": meta.get("file_path", ""),
                "start_line": meta.get("start_line", 0),
                "project_name": meta.get("project_name", ""),
                "distance": candidate["distance"],
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, len(candidates))) as executor:
            formatted = list(executor.map(_load_snippet, candidates))
        
        if not should_re_rank:
            # Already sorted by distance from ChromaDB
            return formatted[:n_results]

        # Re-ranking stage (triggers model loading if it's the first time)
        cross_inp = [[query, item["snippet"]] for item in formatted]
        with redirect_stdout_to_stderr():
            cross_scores = self.cross_encoder.predict(cross_inp)

        for idx, score in enumerate(cross_scores):
            formatted[idx]["cross_encoder_score"] = float(score)

        formatted.sort(key=lambda x: x.get("cross_encoder_score", 0), reverse=True)
        return formatted[:n_results]
