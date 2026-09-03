"""FastAPI routes for conversational BI and SSE streaming."""
import asyncio
import json
from typing import AsyncGenerator, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from naturallangdata.agents.bi_state import BIAgentState

router = APIRouter()


@router.get("/health")
def bi_health(request: Request):
    """Health check reporting storage and fallback statuses."""
    redis_obj = request.app.state.redis_cache
    qdrant_obj = request.app.state.qdrant_schema_store
    return {
        "status": "healthy",
        "redis_fallback": redis_obj.is_fallback,
        "qdrant_fallback": qdrant_obj._is_in_memory,
        "indexed_tables": list(redis_obj.get_all_schemas().keys()),
    }


@router.post("/ingest")
def bi_ingest(request: Request):
    """Manually trigger schema profiling and synchronization into Redis and Qdrant."""
    indexer = request.app.state.schema_indexer
    tables = indexer.index_all()
    return {
        "status": "success",
        "message": f"Successfully indexed {len(tables)} tables.",
        "tables": [t["table_name"] for t in tables],
    }


@router.get("/stream")
async def stream_bi_query(
    request: Request,
    q: str = Query(..., description="Natural language question"),
    engine: Optional[str] = Query(None, description="Optional target engine filter ('duckdb' or 'sqlite')"),
    history: Optional[str] = Query(None, description="Optional JSON-encoded recent chat history"),
):
    """Stream conversational BI query execution traces, validated SQL, data, and charts via SSE."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty")

    chat_history: List[Dict[str, str]] = []
    if history:
        try:
            parsed = json.loads(history)
            if isinstance(parsed, list):
                chat_history = parsed
        except Exception:
            chat_history = []

    print(f"\n{'='*70}", flush=True)
    print(f"[QueryMind/BI API] Incoming Query: {q}", flush=True)
    print(f"[QueryMind/BI API] Engine Requested: {engine or 'AUTO-DETECT'}", flush=True)
    if chat_history:
        print(f"[QueryMind/BI API] Chat History Turns: {len(chat_history)}", flush=True)
    print(f"{'='*70}", flush=True)

    graph = request.app.state.bi_graph

    async def event_generator() -> AsyncGenerator[dict, None]:
        yield {
            "event": "trace",
            "data": json.dumps({"node": "init", "message": f"Initializing workflow for query: '{q}'"}),
        }

        initial_state: BIAgentState = {
            "query": q,
            "target_engine": engine if engine in ("duckdb", "sqlite") else "",
            "retrieved_schemas": [],
            "generated_sql": "",
            "sql_valid": False,
            "error_trace": None,
            "retry_count": 0,
            "data_result": [],
            "chart_spec": {},
            "trace_steps": [],
            "chat_history": chat_history,
        }

        def run_graph_step():
            return list(graph.stream(initial_state))

        try:
            stream_chunks = await asyncio.to_thread(run_graph_step)
        except Exception as exc:
            print(f"[QueryMind/BI API] Workflow invocation error: {exc}", flush=True)
            yield {
                "event": "trace",
                "data": json.dumps({"node": "error", "message": f"Graph execution failure: {exc}"}),
            }
            yield {"event": "done", "data": json.dumps({"status": "failed", "error": str(exc)})}
            return

        last_state = initial_state
        emitted_traces = 0

        for chunk in stream_chunks:
            for node_name, node_state in chunk.items():
                last_state = node_state
                all_traces = node_state.get("trace_steps", [])

                while emitted_traces < len(all_traces):
                    trace_item = all_traces[emitted_traces]
                    yield {
                        "event": "trace",
                        "data": json.dumps(trace_item),
                    }
                    emitted_traces += 1

                if node_name == "validator" and node_state.get("sql_valid"):
                    yield {
                        "event": "sql",
                        "data": json.dumps({
                            "sql": node_state.get("generated_sql", ""),
                            "engine": node_state.get("target_engine", ""),
                        }),
                    }

                if node_name == "executor" and node_state.get("data_result"):
                    yield {
                        "event": "data",
                        "data": json.dumps({
                            "rows": node_state.get("data_result", []),
                            "count": len(node_state.get("data_result", [])),
                        }),
                    }

                if node_name == "visualizer" and node_state.get("chart_spec"):
                    yield {
                        "event": "visualization",
                        "data": json.dumps(node_state.get("chart_spec", {})),
                    }

                if node_name == "narrator" and node_state.get("summary"):
                    yield {
                        "event": "summary",
                        "data": json.dumps({"summary": node_state.get("summary", "")}),
                    }

        if last_state.get("generated_sql") and not last_state.get("sql_valid"):
            yield {
                "event": "sql",
                "data": json.dumps({
                    "sql": last_state.get("generated_sql", ""),
                    "engine": last_state.get("target_engine", ""),
                    "error": last_state.get("error_trace"),
                }),
            }

        yield {
            "event": "done",
            "data": json.dumps({
                "status": "completed" if last_state.get("sql_valid") else "failed",
                "summary": last_state.get("summary", ""),
                "error": last_state.get("error_trace"),
            }),
        }

    return EventSourceResponse(event_generator())
