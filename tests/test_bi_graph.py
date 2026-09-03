"""LangGraph state machine flow and reflection tests for NaturalLangData BI engine."""
import pytest
from data.seed_data import seed_all
from naturallangdata.agents.bi_graph import build_bi_graph
from naturallangdata.agents.bi_state import BIAgentState
from naturallangdata.core.config import Settings
from naturallangdata.core.qdrant_schema_store import QdrantSchemaStore
from naturallangdata.core.redis_cache import RedisCache
from naturallangdata.services.schema_indexer import SchemaIndexer


@pytest.fixture(scope="module")
def prepared_environment():
    """Seed data and initialize test dependencies."""
    seed_all()
    settings = Settings()
    redis_cache = RedisCache(settings)
    qdrant_store = QdrantSchemaStore(settings)

    indexer = SchemaIndexer(settings, redis_cache, qdrant_store)
    indexer.index_all()

    return settings, redis_cache, qdrant_store


def test_end_to_end_graph_execution_duckdb(prepared_environment):
    """Verify end-to-end execution of analytical query against DuckDB."""
    settings, redis_cache, qdrant_store = prepared_environment
    graph = build_bi_graph(settings, redis_cache, qdrant_store)

    initial_state: BIAgentState = {
        "query": "Quarterly ARR trends in EMEA",
        "target_engine": "duckdb",
        "retrieved_schemas": [],
        "generated_sql": "",
        "sql_valid": False,
        "error_trace": None,
        "retry_count": 0,
        "data_result": [],
        "chart_spec": {},
        "trace_steps": [],
    }

    final_state = graph.invoke(initial_state)

    assert final_state["sql_valid"] is True
    assert final_state["target_engine"] == "duckdb"
    assert len(final_state["data_result"]) > 0
    assert "quarterly_arr" in final_state["generated_sql"].lower()
    assert final_state["chart_spec"].get("chartType") in ("line", "bar", "table")
    assert len(final_state["trace_steps"]) >= 4


def test_end_to_end_graph_execution_sqlite(prepared_environment):
    """Verify end-to-end execution of transactional query against SQLite."""
    settings, redis_cache, qdrant_store = prepared_environment
    graph = build_bi_graph(settings, redis_cache, qdrant_store)

    initial_state: BIAgentState = {
        "query": "Active customers in NA",
        "target_engine": "sqlite",
        "retrieved_schemas": [],
        "generated_sql": "",
        "sql_valid": False,
        "error_trace": None,
        "retry_count": 0,
        "data_result": [],
        "chart_spec": {},
        "trace_steps": [],
    }

    final_state = graph.invoke(initial_state)

    assert final_state["sql_valid"] is True
    assert final_state["target_engine"] == "sqlite"
    assert len(final_state["data_result"]) > 0
    assert "customers" in final_state["generated_sql"].lower()


def test_reflection_loop_on_invalid_sql(prepared_environment, monkeypatch):
    """Verify reflection cycle triggers on AST error and increments retry count."""
    settings, redis_cache, qdrant_store = prepared_environment

    attempt_counter = 0

    def faulty_generator(state: BIAgentState) -> BIAgentState:
        nonlocal attempt_counter
        attempt_counter += 1
        if attempt_counter == 1:
            bad_sql = "SELECT invalid_col_xyz FROM customers"
        else:
            bad_sql = "SELECT customer_id, full_name FROM customers LIMIT 5"

        traces = list(state.get("trace_steps", []))
        traces.append({"node": "generator", "sql": bad_sql})
        return {
            **state,
            "generated_sql": bad_sql,
            "trace_steps": traces,
        }

    monkeypatch.setattr("naturallangdata.agents.bi_graph.make_bi_generator_node", lambda s: faulty_generator)

    graph_with_fault = build_bi_graph(settings, redis_cache, qdrant_store)

    state = graph_with_fault.invoke({
        "query": "List customers",
        "target_engine": "sqlite",
        "retrieved_schemas": [],
        "generated_sql": "",
        "sql_valid": False,
        "error_trace": None,
        "retry_count": 0,
        "data_result": [],
        "chart_spec": {},
        "trace_steps": [],
    })

    assert state["retry_count"] >= 1
    assert state["sql_valid"] is True
    assert len(state["data_result"]) > 0
