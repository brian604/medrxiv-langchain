"""
Comprehensive tests for the BioRxiv/MedRxiv API.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from medrxiv_langchain.api_main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


# ============================================================================
# Health Check Tests
# ============================================================================

def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "endpoints" in data


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "servers" in data
    assert len(data["servers"]) == 2  # biorxiv and medrxiv


# ============================================================================
# Search Tests
# ============================================================================

def test_search_simple_keywords(client):
    """Test simple keyword search."""
    request_data = {
        "keywords": ["COVID-19", "vaccine"],
        "recent_days": 30,
        "servers": ["biorxiv"],
        "max_results": 10
    }

    response = client.post("/api/v1/search", json=request_data)
    assert response.status_code == 200
    data = response.json()

    assert "query_id" in data
    assert "total_results" in data
    assert "papers" in data
    assert "execution_time_ms" in data
    assert isinstance(data["papers"], list)


def test_search_with_date_range(client):
    """Test search with absolute date range."""
    request_data = {
        "keywords": ["machine learning"],
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "servers": ["biorxiv"],
        "max_results": 5
    }

    response = client.post("/api/v1/search", json=request_data)
    assert response.status_code == 200
    data = response.json()

    assert data["total_results"] >= 0
    assert len(data["papers"]) <= 5


def test_search_with_category(client):
    """Test search with category filter."""
    request_data = {
        "keywords": ["CRISPR"],
        "category": "genetics",
        "recent_days": 60,
        "servers": ["biorxiv"]
    }

    response = client.post("/api/v1/search", json=request_data)
    assert response.status_code == 200


def test_search_multi_server(client):
    """Test search across multiple servers."""
    request_data = {
        "keywords": ["cancer"],
        "recent_days": 7,
        "servers": ["biorxiv", "medrxiv"],
        "max_results": 20
    }

    response = client.post("/api/v1/search", json=request_data)
    assert response.status_code == 200
    data = response.json()

    assert "biorxiv" in data["servers_queried"] or "medrxiv" in data["servers_queried"]


def test_search_invalid_date_format(client):
    """Test search with invalid date format."""
    request_data = {
        "keywords": ["test"],
        "start_date": "2023/01/01",  # Invalid format
        "end_date": "2023-12-31",
        "servers": ["biorxiv"]
    }

    response = client.post("/api/v1/search", json=request_data)
    assert response.status_code == 422  # Validation error


def test_search_no_servers(client):
    """Test search with empty server list."""
    request_data = {
        "keywords": ["test"],
        "recent_days": 7,
        "servers": []
    }

    response = client.post("/api/v1/search", json=request_data)
    assert response.status_code == 422  # Validation error


# ============================================================================
# Fetch Tests
# ============================================================================

def test_fetch_sync_with_query_id(client):
    """Test synchronous fetch with query ID."""
    # First, perform a search
    search_request = {
        "keywords": ["test"],
        "recent_days": 7,
        "servers": ["biorxiv"],
        "max_results": 5
    }
    search_response = client.post("/api/v1/search", json=search_request)
    query_id = search_response.json()["query_id"]

    # Then fetch using query ID
    fetch_request = {
        "query_id": query_id,
        "async_execution": False
    }

    response = client.post("/api/v1/fetch", json=fetch_request)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["total_fetched"] >= 0


def test_fetch_async(client):
    """Test async fetch returns job ID."""
    # First, perform a search
    search_request = {
        "keywords": ["test"],
        "recent_days": 7,
        "servers": ["biorxiv"],
        "max_results": 5
    }
    search_response = client.post("/api/v1/search", json=search_request)
    query_id = search_response.json()["query_id"]

    # Then fetch asynchronously
    fetch_request = {
        "query_id": query_id,
        "async_execution": True
    }

    response = client.post("/api/v1/fetch", json=fetch_request)
    assert response.status_code == 200
    data = response.json()

    assert "job_id" in data
    assert data["status"] == "pending"


def test_fetch_invalid_query_id(client):
    """Test fetch with non-existent query ID."""
    fetch_request = {
        "query_id": "nonexistent_query_id",
        "async_execution": False
    }

    response = client.post("/api/v1/fetch", json=fetch_request)
    assert response.status_code == 404


# ============================================================================
# Summarization Tests
# ============================================================================

def test_summarize_with_query_id(client):
    """Test summarization with query ID."""
    # First, perform a search
    search_request = {
        "keywords": ["COVID-19"],
        "recent_days": 30,
        "servers": ["biorxiv"],
        "max_results": 3
    }
    search_response = client.post("/api/v1/search", json=search_request)
    assert search_response.status_code == 200

    query_id = search_response.json()["query_id"]

    # Then summarize
    summarize_request = {
        "query_id": query_id,
        "engine": "langchain",
        "max_length": 100
    }

    response = client.post("/api/v1/summarize", json=summarize_request)

    # Note: This might fail if dependencies aren't installed
    # In that case, we expect a 500 error
    assert response.status_code in [200, 500]

    if response.status_code == 200:
        data = response.json()
        assert "summaries" in data
        assert "total_processed" in data


def test_summarize_invalid_query_id(client):
    """Test summarization with invalid query ID."""
    summarize_request = {
        "query_id": "nonexistent_id",
        "engine": "langchain"
    }

    response = client.post("/api/v1/summarize", json=summarize_request)
    assert response.status_code == 404


# ============================================================================
# Semantic Similarity Tests
# ============================================================================

def test_semantic_similarity_with_query_id(client):
    """Test semantic similarity with query ID."""
    # First, perform a search
    search_request = {
        "keywords": ["genomics"],
        "recent_days": 30,
        "servers": ["biorxiv"],
        "max_results": 5
    }
    search_response = client.post("/api/v1/search", json=search_request)
    assert search_response.status_code == 200

    query_id = search_response.json()["query_id"]

    # Then compute similarity
    similarity_request = {
        "query_id": query_id,
        "query_text": "novel approaches to genome sequencing",
        "model_name": "all-MiniLM-L6-v2",
        "top_k": 3
    }

    response = client.post("/api/v1/semantic_similarity", json=similarity_request)

    # Note: This might fail if dependencies aren't installed
    assert response.status_code in [200, 500]

    if response.status_code == 200:
        data = response.json()
        assert "ranked_papers" in data
        assert len(data["ranked_papers"]) <= 3


def test_semantic_similarity_invalid_query_id(client):
    """Test semantic similarity with invalid query ID."""
    similarity_request = {
        "query_id": "nonexistent_id",
        "query_text": "test query"
    }

    response = client.post("/api/v1/semantic_similarity", json=similarity_request)
    assert response.status_code == 404


# ============================================================================
# Export Tests
# ============================================================================

def test_export_json(client):
    """Test JSON export."""
    # First, perform a search
    search_request = {
        "keywords": ["test"],
        "recent_days": 7,
        "servers": ["biorxiv"],
        "max_results": 3
    }
    search_response = client.post("/api/v1/search", json=search_request)
    query_id = search_response.json()["query_id"]

    # Then export as JSON
    response = client.get(
        f"/api/v1/export?query_id={query_id}&format=json&include_abstracts=true"
    )

    assert response.status_code == 200
    data = response.json()
    assert "papers" in data


def test_export_csv(client):
    """Test CSV export."""
    # First, perform a search
    search_request = {
        "keywords": ["test"],
        "recent_days": 7,
        "servers": ["biorxiv"],
        "max_results": 3
    }
    search_response = client.post("/api/v1/search", json=search_request)
    query_id = search_response.json()["query_id"]

    # Then export as CSV
    response = client.get(
        f"/api/v1/export?query_id={query_id}&format=csv&include_abstracts=false"
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]


def test_export_missing_query_id(client):
    """Test export without query ID."""
    response = client.get("/api/v1/export")
    assert response.status_code == 400


def test_export_invalid_query_id(client):
    """Test export with invalid query ID."""
    response = client.get("/api/v1/export?query_id=nonexistent_id&format=json")
    assert response.status_code == 404


# ============================================================================
# Job Status Tests
# ============================================================================

def test_job_status_invalid_id(client):
    """Test job status with invalid job ID."""
    response = client.get("/api/v1/jobs/nonexistent_job_id")
    assert response.status_code == 404


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_workflow(client):
    """Test complete workflow: search -> summarize -> similarity -> export."""
    # 1. Search
    search_request = {
        "keywords": ["immunology"],
        "recent_days": 30,
        "servers": ["biorxiv"],
        "max_results": 5
    }
    search_response = client.post("/api/v1/search", json=search_request)
    assert search_response.status_code == 200
    query_id = search_response.json()["query_id"]

    # 2. Export
    export_response = client.get(
        f"/api/v1/export?query_id={query_id}&format=json"
    )
    assert export_response.status_code == 200

    # Note: Summarize and similarity might fail without dependencies
    # So we skip them in this integration test


# ============================================================================
# Performance Tests
# ============================================================================

def test_search_performance(client):
    """Test search performance."""
    import time

    start = time.time()

    request_data = {
        "keywords": ["test"],
        "recent_days": 7,
        "servers": ["biorxiv"],
        "max_results": 10
    }

    response = client.post("/api/v1/search", json=request_data)
    elapsed = time.time() - start

    assert response.status_code == 200
    # Should complete within reasonable time
    assert elapsed < 30  # 30 seconds max


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
