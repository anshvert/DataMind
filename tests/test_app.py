"""Smoke tests for the refactored NaturalLangData API."""
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    """Return a TestClient with all external services mocked out."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    # Prevent real Qdrant connection during tests
    with patch("naturallangdata.services.qdrant_service.QdrantService.ensure_collection"), \
         patch("naturallangdata.services.qdrant_service.QdrantService.health", return_value="ok"), \
         patch("app.build_ingestion_graph", return_value=MagicMock()), \
         patch("app.build_query_graph", return_value=MagicMock()):
        from app import create_app
        test_app = create_app()
        with TestClient(test_app) as c:
            yield c


# ── tests ─────────────────────────────────────────────────────────────────────

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "NaturalLangData" in response.text


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["qdrant"] == "ok"


def test_config_reads_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
    monkeypatch.setenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
    monkeypatch.setenv("CHAT_MODEL", "openai/gpt-4o-mini")
    from naturallangdata.core.config import Settings
    s = Settings()
    assert s.openrouter_api_key == "sk-test-123"
    assert s.embedding_model == "qwen/qwen3-embedding-8b"
    assert s.chat_model == "openai/gpt-4o-mini"


def test_embeddings_service_init(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    from naturallangdata.core.config import Settings
    from naturallangdata.services.embeddings import EmbeddingsService
    svc = EmbeddingsService(Settings())
    assert svc._model == "qwen/qwen3-embedding-8b"
