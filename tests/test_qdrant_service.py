from types import SimpleNamespace

from naturallangdata.core.config import Settings
from naturallangdata.services.qdrant_service import QdrantService


class DummyClient:
    def __init__(self):
        self.last_call = None

    def query_points(self, **kwargs):
        self.last_call = kwargs
        hit = SimpleNamespace(
            payload={
                "doc_id": "doc_1",
                "doc_name": "sample",
                "chunk_text": "hello world",
            },
            score=0.91,
        )
        return SimpleNamespace(points=[hit])


def test_search_uses_query_points(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    settings = Settings()
    service = QdrantService(settings)

    dummy = DummyClient()
    service._client = dummy

    results = service.search(query_vector=[0.1, 0.2, 0.3], limit=3, doc_id_filter="doc_1")

    assert dummy.last_call is not None
    assert dummy.last_call["collection_name"] == settings.qdrant_collection
    assert dummy.last_call["query"] == [0.1, 0.2, 0.3]
    assert dummy.last_call["limit"] == 3
    assert results[0]["doc_id"] == "doc_1"
    assert results[0]["doc_name"] == "sample"
    assert results[0]["text"] == "hello world"
