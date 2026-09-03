"""LangGraph StateGraph assembly for Conversational BI workflow."""
from typing import Literal
from langgraph.graph import END, START, StateGraph

from naturallangdata.agents.bi_state import BIAgentState
from naturallangdata.agents.nodes.bi.executor import make_bi_executor_node
from naturallangdata.agents.nodes.bi.generator import make_bi_generator_node
from naturallangdata.agents.nodes.bi.narrator import make_bi_narrator_node
from naturallangdata.agents.nodes.bi.reflection import make_bi_reflection_node
from naturallangdata.agents.nodes.bi.router import make_bi_router_node
from naturallangdata.agents.nodes.bi.validator import make_bi_validator_node
from naturallangdata.agents.nodes.bi.visualizer import make_bi_visualizer_node
from naturallangdata.core.config import Settings
from naturallangdata.core.qdrant_schema_store import QdrantSchemaStore
from naturallangdata.core.redis_cache import RedisCache


def route_post_validation(state: BIAgentState) -> Literal["executor", "reflection", "visualizer"]:
    """Determine next step after AST validation."""
    if state.get("sql_valid"):
        return "executor"
    if state.get("retry_count", 0) < 2:
        return "reflection"
    return "visualizer"


def route_post_execution(state: BIAgentState) -> Literal["visualizer", "reflection"]:
    """Determine next step after query execution."""
    if state.get("error_trace") is None:
        return "visualizer"
    if state.get("retry_count", 0) < 2:
        return "reflection"
    return "visualizer"


def build_bi_graph(
    settings: Settings,
    redis_cache: RedisCache,
    qdrant_store: QdrantSchemaStore,
):
    """Assemble and compile the StateGraph workflow."""
    builder = StateGraph(BIAgentState)

    builder.add_node("router", make_bi_router_node(qdrant_store, redis_cache))
    builder.add_node("generator", make_bi_generator_node(settings))
    builder.add_node("validator", make_bi_validator_node(redis_cache))
    builder.add_node("reflection", make_bi_reflection_node(settings.max_reflections))
    builder.add_node("executor", make_bi_executor_node(settings))
    builder.add_node("visualizer", make_bi_visualizer_node())
    builder.add_node("narrator", make_bi_narrator_node(settings))

    builder.add_edge(START, "router")
    builder.add_edge("router", "generator")
    builder.add_edge("generator", "validator")

    builder.add_conditional_edges(
        "validator",
        route_post_validation,
        {
            "executor": "executor",
            "reflection": "reflection",
            "visualizer": "visualizer",
        },
    )

    builder.add_edge("reflection", "generator")

    builder.add_conditional_edges(
        "executor",
        route_post_execution,
        {
            "visualizer": "visualizer",
            "reflection": "reflection",
        },
    )

    builder.add_edge("visualizer", "narrator")
    builder.add_edge("narrator", END)

    return builder.compile()
