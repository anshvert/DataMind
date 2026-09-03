"""Integration tests for NaturalLangData unified BI endpoints."""
from fastapi.testclient import TestClient
import pytest
from app import create_app
from data.seed_data import seed_all


@pytest.fixture(scope="module")
def test_client():
    """Create a TestClient with seeded datasets."""
    seed_all()
    application = create_app()
    with TestClient(application) as client:
        yield client


def test_bi_health_endpoint(test_client):
    """Verify BI health endpoint returns healthy status and indexed tables."""
    response = test_client.get("/bi/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "quarterly_arr" in body["indexed_tables"] or "customers" in body["indexed_tables"]


def test_root_serves_frontend_with_bi(test_client):
    """Verify root path serves HTML frontend with ECharts and stepper."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert "DataMind" in response.text or "NaturalLangData" in response.text
    assert "echarts" in response.text
    assert "execution-stepper" in response.text


def test_manual_bi_ingest_endpoint(test_client):
    """Verify manual schema ingestion endpoint."""
    response = test_client.post("/bi/ingest")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert len(body["tables"]) >= 3


def test_sse_bi_query_stream(test_client):
    """Verify SSE query stream emits trace, sql, data, and done events."""
    with test_client.stream("GET", "/bi/stream?q=Quarterly+ARR+trends+in+EMEA") as response:
        assert response.status_code == 200
        content = response.read().decode("utf-8")
        assert "event: trace" in content
        assert "event: sql" in content
        assert "event: data" in content
        assert "event: done" in content


def test_upload_parquet_analytical_data(test_client, tmp_path):
    """Verify uploading parquet files automatically routes to analytics store and indexes schema."""
    import duckdb
    import pandas as pd
    test_df = pd.DataFrame([{"team": "Core", "velocity": 42}, {"team": "UI", "velocity": 38}])
    parquet_file = tmp_path / "team_velocity.parquet"
    duckdb.sql("SELECT * FROM test_df").write_parquet(str(parquet_file))

    with open(parquet_file, "rb") as f:
        response = test_client.post(
            "/documents/upload",
            files={"file": ("team_velocity.parquet", f, "application/octet-stream")},
        )
    assert response.status_code == 201
    body = response.json()
    assert "Analytical dataset ingested" in body["message"]
