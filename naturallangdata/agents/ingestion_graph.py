"""Ingestion pipeline (LangGraph).

Topology
--------
START → master → extract_text → chunk_text → embed_chunks → ingest → END

Every node sets state["status"] = "error" on failure.
Conditional edges bail out to END immediately when an error is detected so the
API layer can inspect the final state and return a proper HTTP error.
"""
from typing import Literal

from langgraph.graph import END, START, StateGraph

from naturallangdata.agents.nodes.chunking import make_chunk_text_node
from naturallangdata.agents.nodes.embedding import make_embed_chunks_node
from naturallangdata.agents.nodes.extraction import make_extract_text_node
from naturallangdata.agents.nodes.ingestion import make_ingest_node
from naturallangdata.agents.nodes.master import ingestion_master_node
from naturallangdata.agents.state import IngestionState
from naturallangdata.core.config import Settings
from naturallangdata.services.document_extractor import DocumentExtractionService
from naturallangdata.services.embeddings import EmbeddingsService
from naturallangdata.services.qdrant_service import QdrantService


def _route(state: IngestionState) -> Literal["continue", "end"]:
    return "end" if state.get("status") == "error" else "continue"


def build_ingestion_graph(
    settings: Settings,
    embeddings: EmbeddingsService,
    qdrant: QdrantService,
    document_extractor: DocumentExtractionService,
):
    graph = StateGraph(IngestionState)

    graph.add_node("master", ingestion_master_node)
    graph.add_node("extract_text", make_extract_text_node(extract_text_fn=document_extractor.extract))
    graph.add_node(
        "chunk_text",
        make_chunk_text_node(
            embed_fn=embeddings.embed_documents,
            breakpoint_threshold=settings.chunk_breakpoint_threshold,
            min_size=settings.chunk_min_size,
            max_size=settings.chunk_max_size,
        ),
    )
    graph.add_node("embed_chunks", make_embed_chunks_node(embed_fn=embeddings.embed_documents))
    graph.add_node("ingest", make_ingest_node(qdrant=qdrant))

    graph.add_edge(START, "master")
    graph.add_conditional_edges("master", _route, {"continue": "extract_text", "end": END})
    graph.add_conditional_edges("extract_text", _route, {"continue": "chunk_text", "end": END})
    graph.add_conditional_edges("chunk_text", _route, {"continue": "embed_chunks", "end": END})
    graph.add_conditional_edges("embed_chunks", _route, {"continue": "ingest", "end": END})
    graph.add_edge("ingest", END)

    return graph.compile()
