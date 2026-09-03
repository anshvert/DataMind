"""Router node for Schema RAG retrieval and engine selection."""
from typing import Any, Callable, Dict, List
from naturallangdata.agents.bi_state import BIAgentState
from naturallangdata.core.qdrant_schema_store import QdrantSchemaStore
from naturallangdata.core.redis_cache import RedisCache


def make_bi_router_node(
    qdrant_store: QdrantSchemaStore,
    redis_cache: RedisCache,
) -> Callable[[BIAgentState], BIAgentState]:
    """Create a router node instance with injected vector and cache dependencies."""

    def router_node(state: BIAgentState) -> BIAgentState:
        query = state.get("query", "")
        traces: List[Dict[str, Any]] = list(state.get("trace_steps", []))
        engine_override = state.get("target_engine")
        history = state.get("chat_history", [])

        query_lower = query.lower()

        known_entity_keywords = [
            "customer", "order", "signup", "inventory", "product", "sku",
            "arr", "churn", "velocity", "environmental", "expenditure", "protection"
        ]
        has_direct_entity = any(term in query_lower for term in known_entity_keywords)

        followup_signals = [
            "it", "they", "those", "that", "these", "now give", "what about",
            "break it down", "and for", "also show", "same", "between", "next"
        ]
        is_followup = any(sig in query_lower for sig in followup_signals) or len(query.split()) <= 4

        if is_followup and history and not has_direct_entity:
            history_text = " ".join(item.get("text", "") for item in history[-2:])
            search_query = f"{history_text} {query}".strip()
        else:
            search_query = query

        schemas = qdrant_store.search_schemas(search_query, top_k=5)

        if not schemas:
            all_cached = redis_cache.get_all_schemas()
            schemas = list(all_cached.values())[:5]

        if engine_override in ("duckdb", "sqlite"):
            target_engine = engine_override
            filtered_schemas = [s for s in schemas if s.get("engine") == target_engine]
            if not filtered_schemas:
                all_cached = redis_cache.get_all_schemas()
                filtered_schemas = [s for s in all_cached.values() if s.get("engine") == target_engine][:3]
            schemas = filtered_schemas or schemas
        else:
            top_schema = schemas[0] if schemas else None

            if any(term in query_lower for term in ["customer", "order", "signup"]):
                target_engine = "sqlite"
            elif any(term in query_lower for term in ["arr", "revenue", "churn", "inventory", "stock", "sku", "parquet", "csv", "environmental", "expenditure"]):
                target_engine = "duckdb"
            elif top_schema and top_schema.get("engine"):
                target_engine = top_schema["engine"]
            else:
                target_engine = "duckdb" if any(s.get("engine") == "duckdb" for s in schemas) else "sqlite"

        schema_names = [s.get("table_name", "") for s in schemas]

        print(f"\n[DataMind Router] Question: {query}", flush=True)
        if search_query != query:
            print(f"[DataMind Router] Contextual Search Query: {search_query[:120]}...", flush=True)
        print(f"[DataMind Router] Retrieved Schemas: {schema_names}", flush=True)
        print(f"[DataMind Router] Selected Engine: {target_engine.upper()}", flush=True)

        traces.append({
            "node": "router",
            "message": f"Retrieved schemas: {', '.join(schema_names)} | Engine: {target_engine}",
            "schemas": schema_names,
            "engine": target_engine,
        })

        return {
            **state,
            "retrieved_schemas": schemas,
            "target_engine": target_engine,
            "trace_steps": traces,
        }

    return router_node
