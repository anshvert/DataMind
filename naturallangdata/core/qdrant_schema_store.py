"""Qdrant schema vector store wrapper with in-memory fallback for Schema RAG."""
import hashlib
import math
import re
from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from naturallangdata.core.config import Settings


class QdrantSchemaStore:
    """Vector database manager for table schema semantic search."""

    def __init__(self, settings: Settings) -> None:
        self._url = settings.qdrant_url
        self._collection = settings.qdrant_bi_collection
        self._dim = 384
        self._is_in_memory = False
        self._client: Optional[QdrantClient] = None
        self._local_docs: List[Dict[str, Any]] = []
        self._connect()

    def _connect(self) -> None:
        try:
            client = QdrantClient(url=self._url, timeout=1.5, check_compatibility=False)
            client.get_collections()
            self._client = client
            self._is_in_memory = False
            self._ensure_collection()
        except Exception:
            try:
                self._client = QdrantClient(":memory:")
                self._is_in_memory = False
                self._ensure_collection()
            except Exception:
                self._client = None
                self._is_in_memory = True

    def _ensure_collection(self) -> None:
        if self._client:
            try:
                collections = [c.name for c in self._client.get_collections().collections]
                if self._collection not in collections:
                    self._client.create_collection(
                        collection_name=self._collection,
                        vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
                    )
            except Exception:
                self._is_in_memory = True

    def _generate_vector(self, text: str) -> List[float]:
        tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
        vec = [0.0] * self._dim
        if not tokens:
            return vec
        for token in tokens:
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def upsert_schema(
        self,
        table_name: str,
        engine: str,
        description: str,
        columns: List[str],
        ddl: str,
    ) -> None:
        """Embed and upsert table schema metadata."""
        search_text = f"{table_name} {engine} {description} {' '.join(columns)}"
        vector = self._generate_vector(search_text)
        point_id = int(hashlib.md5(f"{engine}:{table_name}".encode("utf-8")).hexdigest()[:8], 16)

        payload = {
            "table_name": table_name,
            "engine": engine,
            "description": description,
            "columns": columns,
            "ddl": ddl,
        }

        if self._client and not self._is_in_memory:
            try:
                self._client.upsert(
                    collection_name=self._collection,
                    points=[PointStruct(id=point_id, vector=vector, payload=payload)],
                )
                return
            except Exception:
                self._is_in_memory = True

        self._local_docs = [d for d in self._local_docs if d["payload"]["table_name"] != table_name]
        self._local_docs.append({"id": point_id, "vector": vector, "payload": payload})

    def search_schemas(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve the top matching table schemas using vector similarity."""
        vector = self._generate_vector(query)

        if self._client and not self._is_in_memory:
            try:
                if hasattr(self._client, "query_points"):
                    res = self._client.query_points(
                        collection_name=self._collection,
                        query=vector,
                        limit=top_k,
                    )
                    return [p.payload for p in res.points if p.payload]
                elif hasattr(self._client, "search"):
                    results = self._client.search(
                        collection_name=self._collection,
                        query_vector=vector,
                        limit=top_k,
                    )
                    return [r.payload for r in results if r.payload]
            except Exception:
                self._is_in_memory = True

        scored: List[tuple[float, Dict[str, Any]]] = []
        for item in self._local_docs:
            item_vec = item["vector"]
            dot_product = sum(a * b for a, b in zip(vector, item_vec))
            tokens_in_payload = (
                item["payload"]["table_name"].lower()
                + " "
                + item["payload"]["description"].lower()
                + " "
                + " ".join(item["payload"]["columns"]).lower()
            )
            query_words = re.findall(r"[a-zA-Z0-9]+", query.lower())
            overlap = sum(1.0 for w in query_words if w in tokens_in_payload)
            final_score = dot_product + (0.2 * overlap)
            scored.append((final_score, item["payload"]))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [payload for _, payload in scored[:top_k]]
