"""Semantic search queries against ChromaDB."""
import logging
from typing import Any, Dict, List, Optional, Union

import chromadb
from chromadb.utils import embedding_functions
from config import config

logger = logging.getLogger(__name__)


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

    def search(
        self,
        query: str,
        n_results: int = 3,
        project_name: Optional[
            Union[str, List[str]]
        ] = None,
        max_distance: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Query ChromaDB for relevant code snippets.

        Args:
            query: Natural language search query.
            n_results: Max number of results.
            project_name: Filter by project(s).
            max_distance: Override distance threshold.
        """
        collection_count = self.collection.count()
        if collection_count == 0:
            return []
        n_results = min(n_results, collection_count)

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
            n_results=n_results,
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

        for doc, meta, dist in zip(
            docs, metas, distances
        ):
            if dist is not None and dist > threshold:
                continue

            snippet = doc
            # If doc is missing from DB, load it from the chunks folder
            if not snippet and meta and meta.get("chunk_file"):
                try:
                    with open(
                        meta["chunk_file"], "r", encoding="utf-8"
                    ) as f:
                        snippet = f.read()
                except Exception as e:
                    logger.warning(
                        "Could not read chunk file %s: %s",
                        meta["chunk_file"], e,
                    )
                    snippet = "[Content could not be loaded]"

            formatted.append({
                "snippet": snippet,
                "file_path": meta.get(
                    "file_path", ""
                ),
                "start_line": meta.get(
                    "start_line", 0
                ),
                "project_name": meta.get(
                    "project_name", ""
                ),
                "distance": dist,
            })

        return formatted
