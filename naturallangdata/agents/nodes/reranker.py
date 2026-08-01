import logging
from typing import Callable, List

from naturallangdata.agents.state import QueryState

logger = logging.getLogger(__name__)


def make_rerank_node(
    top_n: int,
    rerank_fn: Callable[[str, List[dict], int], List[dict]],
):
    def rerank_node(state: QueryState) -> QueryState:
        docs = state.get("retrieved_docs", [])
        if not docs:
            logger.info("reranker.skipped reason=no_candidates")
            return {**state, "reranked_docs": [], "status": "generating"}

        try:
            logger.info("reranker.input candidates=%d top_n=%d", len(docs), top_n)
            for i, doc in enumerate(docs[: min(10, len(docs))], start=1):
                logger.info(
                    "reranker.pre rank=%d score=%.4f doc=%s text=%r",
                    i,
                    float(doc.get("score", 0.0)),
                    doc.get("doc_name", "unknown"),
                    (doc.get("text", "")[:220]).replace("\n", " "),
                )

            reranked = rerank_fn(state["question"], docs, top_n)
            for i, doc in enumerate(reranked[: min(top_n, len(reranked))], start=1):
                logger.info(
                    "reranker.post rank=%d rerank_score=%.4f doc=%s text=%r",
                    i,
                    float(doc.get("rerank_score", 0.0)),
                    doc.get("doc_name", "unknown"),
                    (doc.get("text", "")[:220]).replace("\n", " "),
                )
            return {**state, "reranked_docs": reranked, "status": "generating"}
        except Exception as exc:
            logger.exception("reranker.failed error=%s", exc)
            # Fall back gracefully — still provide an answer
            return {
                **state,
                "reranked_docs": docs[:top_n],
                "status": "generating",
                "error": f"reranker warning (fell back to vector rank): {exc}",
            }

    return rerank_node
