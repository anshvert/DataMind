import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException

from naturallangdata.agents.state import QueryState
from naturallangdata.api.dependencies import QueryGraphDep
from naturallangdata.models.schemas import QueryRequest, QueryResponse, SourceChunk

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=QueryResponse)
async def query(request: QueryRequest, query_graph: QueryGraphDep = None):
    start = time.perf_counter()
    logger.info(
        "query.received question=%r doc_filter=%s",
        request.question[:120],
        request.doc_id or "ALL",
    )

    initial_state: QueryState = {
        "question": request.question,
        "doc_id_filter": request.doc_id,
        "retrieved_docs": [],
        "reranked_docs": [],
        "answer": "",
        "sources": [],
        "status": "pending",
        "error": None,
    }

    final_state: QueryState = await asyncio.to_thread(
        query_graph.invoke, initial_state
    )

    if final_state.get("status") == "error":
        logger.error(
            "query.failed duration_ms=%.2f error=%s",
            (time.perf_counter() - start) * 1000,
            final_state.get("error", "unknown"),
        )
        raise HTTPException(
            status_code=422,
            detail=final_state.get("error", "Query pipeline failed"),
        )

    sources = [
        SourceChunk(
            doc_id=s["doc_id"],
            doc_name=s["doc_name"],
            text=s["text"],
            score=float(s.get("score", 0.0)),
        )
        for s in final_state.get("sources", [])
    ]
    logger.info(
        "query.completed duration_ms=%.2f sources=%d",
        (time.perf_counter() - start) * 1000,
        len(sources),
    )
    return QueryResponse(
        question=request.question,
        answer=final_state["answer"],
        sources=sources,
    )
