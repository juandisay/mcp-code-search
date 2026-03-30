"""Semantic search queries against ChromaDB."""
import concurrent.futures
import contextlib
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import CrossEncoder

from core.db_utils import get_collection_name  # Add this

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

        # Priority 1: Hybrid Search (FTS5)
        self.state_db_path = Path(self.config.CHROMA_DATA_PATH) / self.config.STATE_DB_NAME

    def _get_db_conn(self) -> sqlite3.Connection:
        """Get a read-only SQLite connection for FTS5 queries."""
        db_uri = f"file:{self.state_db_path}?mode=ro"
        return sqlite3.connect(db_uri, uri=True)

    def shutdown(self):
        """Release ChromaDB and SQLite resources (Pillar III HARDENING)."""
        logger.info("Closing CodeSearcher connections...")
        self.collection = None
        self.chroma_client = None

    def _fts5_search(
        self,
        query: str,
        n_results: int = 20,
        project_name: Optional[Union[str, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform keyword search using SQLite FTS5."""
        try:
            with self._get_db_conn() as conn:
                conn.row_factory = sqlite3.Row

                # Sanitize query for FTS5 (basic escaping)
                # FTS5 doesn't like some characters unless quoted
                safe_query = query.replace('"', '""')

                sql = """
                    SELECT chunk_id, file_path, project_name, content, rank
                    FROM chunk_fts
                    WHERE chunk_fts MATCH ?
                """
                params = [f'"{safe_query}"']

                if project_name:
                    if isinstance(project_name, list):
                        placeholders = ",".join(["?"] * len(project_name))
                        sql += f" AND project_name IN ({placeholders})"
                        params.extend(project_name)
                    else:
                        sql += " AND project_name = ?"
                        params.append(project_name)

                sql += " ORDER BY rank LIMIT ?"
                params.append(n_results * 2) # Get more candidates for RRF

                cursor = conn.execute(sql, params)
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "chunk_id": row["chunk_id"],
                        "file_path": row["file_path"],
                        "project_name": row["project_name"],
                        "content": row["content"],
                        "rank_score": row["rank"] # SQLite FTS5 rank (lower is better)
                    })
                return results
        except Exception as e:
            logger.error("FTS5 search failed: %s", e)
            return []

    def _rrf_merge(
        self,
        vector_results: List[Dict[str, Any]],
        fts_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """Merge results using Reciprocal Rank Fusion (RRF)."""
        scores: Dict[str, float] = {}
        # Keep track of metadata for the winner chunks
        metadata_map: Dict[str, Dict[str, Any]] = {}

        # Process Vector results
        for i, res in enumerate(vector_results):
            # In Chroma, ids are file_path_chunk_i
            # But let's use the actual id if available or metadata
            cid = res.get("id") or f"{res['meta']['file_path']}_chunk_{res['meta'].get('chunk_index', i)}"
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + i + 1)
            metadata_map[cid] = {
                "doc": res["doc"],
                "meta": res["meta"],
                "distance": res.get("distance")
            }

        # Process FTS results
        for i, res in enumerate(fts_results):
            cid = res["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + i + 1)
            if cid not in metadata_map:
                metadata_map[cid] = {
                    "doc": res["content"],
                    "meta": {
                        "file_path": res["file_path"],
                        "project_name": res["project_name"],
                        "extension": Path(res["file_path"]).suffix
                    },
                    "distance": None # FTS doesn't have vector distance
                }

        # Sort by RRF score descending
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        final_results = []
        for cid in sorted_ids:
            item = metadata_map[cid]
            final_results.append(item)

        return final_results

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
        use_hybrid: Optional[bool] = None, # Priority 1: Hybrid Search
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB and SQLite FTS5 for relevant code snippets.

        Args:
            query: Natural language search query.
            n_results: Max number of results.
            project_name: Filter by project(s).
            max_distance: Override distance threshold.
            language: Filter by file extension(s).
            file_path_includes: Require a specific substring in file path.
            excluded_dirs: Exclude directories from search.
            re_rank: Whether to use cross-encoder reranking.
            use_hybrid: Whether to use Hybrid Search (Vector + FTS5).
        """
        collection_count = self.collection.count()
        if collection_count == 0:
            return []

        should_re_rank = re_rank if re_rank is not None else self.config.USE_RERANKER
        should_use_hybrid = use_hybrid if use_hybrid is not None else self.config.USE_HYBRID_SEARCH

        # Stage 1: Fetch larger candidate pool if re-ranking, or exactly n_results if not
        if should_re_rank or should_use_hybrid:
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

        where_clause = None
        if len(where_conditions) == 1:
            where_clause = where_conditions[0]
        elif len(where_conditions) > 1:
            where_clause = {"$and": where_conditions}

        # Pillar I & Priority 1: Parallel Search
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # 1. Vector Search
            vector_future = executor.submit(
                self.collection.query,
                query_texts=[query],
                n_results=initial_k,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )

            # 2. FTS5 Search (if hybrid enabled)
            fts_future = None
            if should_use_hybrid:
                fts_future = executor.submit(
                    self._fts5_search,
                    query=query,
                    n_results=initial_k,
                    project_name=project_name
                )

            # Wait for results
            try:
                results = vector_future.result()
            except Exception as e:
                logger.error("Vector search failed: %s", e)
                results = None

            fts_results = []
            if fts_future:
                try:
                    fts_results = fts_future.result()
                except Exception as e:
                    logger.error("FTS5 search failed: %s", e)

        threshold = (
            max_distance
            if max_distance is not None
            else self.max_distance
        )

        docs_list = (results or {}).get("documents")
        candidates: List[Dict[str, Any]] = []

        if docs_list and docs_list[0]:
            docs = docs_list[0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [None] * len(docs)
            ids = results["ids"][0] if results.get("ids") else [None] * len(docs)

            for doc, meta, dist, cid in zip(docs, metas, distances, ids):
                if dist is not None and dist > threshold:
                    continue

                file_path = meta.get("file_path", "")

                # Stage 1.5: Python-level Filtering
                if file_path_includes and file_path_includes not in file_path:
                    continue

                if excluded_dirs:
                    ex_dirs = excluded_dirs if isinstance(excluded_dirs, list) else [excluded_dirs]
                    if any(f"/{d.strip('/')}/" in f"/{file_path.strip('/')}/" for d in ex_dirs):
                        continue

                candidates.append({
                    "id": cid,
                    "doc": doc,
                    "meta": meta,
                    "distance": dist
                })

        # Merge with FTS5 using RRF if hybrid
        if should_use_hybrid:
            # Filter FTS results for language and file_path_includes since FTS query was basic
            filtered_fts = []
            for res in fts_results:
                fp = res["file_path"]
                ext = Path(fp).suffix

                if language:
                    langs = language if isinstance(language, list) else [language]
                    langs = [ext if ext.startswith('.') else f".{ext}" for ext in langs]
                    if ext not in langs:
                        continue

                if file_path_includes and file_path_includes not in fp:
                    continue

                if excluded_dirs:
                    ex_dirs = excluded_dirs if isinstance(excluded_dirs, list) else [excluded_dirs]
                    if any(f"/{d.strip('/')}/" in f"/{fp.strip('/')}/" for d in ex_dirs):
                        continue

                filtered_fts.append(res)

            merged_candidates = self._rrf_merge(candidates, filtered_fts, k=self.config.RRF_K)
        else:
            merged_candidates = candidates

        if not merged_candidates:
            return []

        # Format results
        formatted = []
        for cand in merged_candidates:
            meta = cand["meta"]
            formatted.append({
                "snippet": cand["doc"] or "",
                "file_path": meta.get("file_path", ""),
                "start_line": meta.get("start_line", 0),
                "project_name": meta.get("project_name", ""),
                "distance": cand.get("distance"),
            })

        if not should_re_rank:
            return formatted[:n_results]

        # Re-ranking stage
        cross_inp = [[query, item["snippet"]] for item in formatted]
        with redirect_stdout_to_stderr():
            cross_scores = self.cross_encoder.predict(cross_inp)

        for idx, score in enumerate(cross_scores):
            formatted[idx]["cross_encoder_score"] = float(score)

        formatted.sort(key=lambda x: x.get("cross_encoder_score", 0), reverse=True)
        return formatted[:n_results]
