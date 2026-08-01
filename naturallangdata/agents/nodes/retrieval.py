"""Retrieval node — question → top-K candidate chunks from Qdrant."""
import logging
from typing import Callable, List

from naturallangdata.agents.state import QueryState
from naturallangdata.services.qdrant_service import QdrantService


logger = logging.getLogger(__name__)


def make_retrieve_node(
    embed_query_fn: Callable[[str], List[float]],
    qdrant: QdrantService,
    top_k: int,
):
    def retrieve_node(state: QueryState) -> QueryState:
        try:
            query_vector = embed_query_fn(state["question"])
            results = qdrant.search(
                query_vector=query_vector,
                limit=top_k,
                doc_id_filter=state.get("doc_id_filter"),
            )

            logger.info(
                "retrieval.complete question=%r doc_filter=%s candidates=%d",
                state["question"][:120],
                state.get("doc_id_filter") or "ALL",
                len(results),
            )
            for i, doc in enumerate(results[: min(10, len(results))], start=1):
                logger.info(
                    "retrieval.chunk rank=%d score=%.4f doc=%s text=%r",
                    i,
                    float(doc.get("score", 0.0)),
                    doc.get("doc_name", "unknown"),
                    (doc.get("text", "")[:220]).replace("\n", " "),
                )

            return {**state, "retrieved_docs": results, "status": "reranking"}
        except Exception as exc:
            return {**state, "status": "error", "error": f"retrieval failed: {exc}"}

    return retrieve_node
