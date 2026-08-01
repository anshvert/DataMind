"""Ingestion node — store chunks + vectors in Qdrant."""
from naturallangdata.agents.state import IngestionState
from naturallangdata.services.qdrant_service import QdrantService


def make_ingest_node(qdrant: QdrantService):
    def ingest_node(state: IngestionState) -> IngestionState:
        try:
            count = qdrant.upsert_chunks(
                doc_id=state["doc_id"],
                doc_name=state["doc_name"],
                source_path=state["source_path"],
                chunks=state["chunks"],
                embeddings=state["embeddings"],
            )
            return {**state, "chunks_count": count, "status": "done"}
        except Exception as exc:
            return {**state, "status": "error", "error": f"qdrant ingestion failed: {exc}"}

    return ingest_node
