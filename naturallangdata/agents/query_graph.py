"""Query pipeline (LangGraph).

Topology
--------
START → master → retrieve → rerank → generate → END

Dense retrieval (Qdrant) → cross-encoder reranking → LLM generation.
"""
from typing import Literal

from langgraph.graph import END, START, StateGraph

from naturallangdata.agents.nodes.generation import make_generation_node
from naturallangdata.agents.nodes.master import query_master_node
from naturallangdata.agents.nodes.reranker import make_rerank_node
from naturallangdata.agents.nodes.retrieval import make_retrieve_node
from naturallangdata.agents.state import QueryState
from naturallangdata.core.config import Settings
from naturallangdata.services.embeddings import EmbeddingsService
from naturallangdata.services.qdrant_service import QdrantService
from naturallangdata.services.reranker import OpenRouterRerankerService


def _route(state: QueryState) -> Literal["continue", "end"]:
    return "end" if state.get("status") == "error" else "continue"


def build_query_graph(
    settings: Settings,
    embeddings: EmbeddingsService,
    qdrant: QdrantService,
    reranker: OpenRouterRerankerService,
):
    graph = StateGraph(QueryState)

    graph.add_node("master", query_master_node)
    graph.add_node(
        "retrieve",
        make_retrieve_node(
            embed_query_fn=embeddings.embed_query,
            qdrant=qdrant,
            top_k=settings.retrieval_top_k,
        ),
    )
    graph.add_node(
        "rerank",
        make_rerank_node(
            top_n=settings.rerank_top_n,
            rerank_fn=reranker.rerank,
        ),
    )
    graph.add_node("generate", make_generation_node(settings=settings))

    graph.add_edge(START, "master")
    graph.add_conditional_edges("master", _route, {"continue": "retrieve", "end": END})
    graph.add_conditional_edges("retrieve", _route, {"continue": "rerank", "end": END})
    graph.add_conditional_edges("rerank", _route, {"continue": "generate", "end": END})
    graph.add_edge("generate", END)

    return graph.compile()
