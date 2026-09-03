import uuid
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from naturallangdata.core.config import Settings


class QdrantService:
    """All Qdrant operations in one place."""

    def __init__(self, settings: Settings) -> None:
        self._client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
        self._collection = settings.qdrant_collection
        self._dim = settings.embedding_dim

    # ── Setup ─────────────────────────────────────────────────────────────────

    def ensure_collection(self) -> None:
        """Create the collection only if it does not already exist."""
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=self._dim,
                    distance=Distance.COSINE,
                ),
            )

    # ── Write ─────────────────────────────────────────────────────────────────

    def upsert_chunks(
        self,
        doc_id: str,
        doc_name: str,
        source_path: str,
        chunks: List[str],
        embeddings: List[List[float]],
    ) -> int:
        """Persist chunks with their embeddings. Returns the number of points stored."""
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "source_path": source_path,
                    "chunk_text": chunk,
                    "chunk_index": idx,
                },
            )
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        self._client.upsert(collection_name=self._collection, points=points)
        return len(points)

    def delete_document(self, doc_id: str) -> None:
        """Remove every chunk that belongs to a document."""
        self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                )
            ),
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(
        self,
        query_vector: List[float],
        limit: int = 20,
        doc_id_filter: Optional[str] = None,
    ) -> List[dict]:
        """Vector search with an optional per-document filter."""
        query_filter: Optional[Filter] = None
        if doc_id_filter:
            query_filter = Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id_filter))]
            )

        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        results = getattr(response, "points", response)
        return [
            {
                "doc_id": r.payload["doc_id"],
                "doc_name": r.payload["doc_name"],
                "text": r.payload["chunk_text"],
                "score": r.score,
            }
            for r in results
        ]

    def list_documents(self) -> List[dict]:
        """Return one record per unique document stored in the collection."""
        points, _ = self._client.scroll(
            collection_name=self._collection,
            with_payload=["doc_id", "doc_name"],
            limit=2000,  # increase when scale demands pagination
        )
        seen: dict[str, str] = {}
        for point in points:
            did = point.payload["doc_id"]
            if did not in seen:
                seen[did] = point.payload["doc_name"]
        return [{"doc_id": did, "name": name} for did, name in seen.items()]

    # ── Health ────────────────────────────────────────────────────────────────

    def health(self) -> str:
        try:
            self._client.get_collections()
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"
