def test_health_returns_expected_fields(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "ollama": "available",
        "ollama_model": "qwen3:4b",
        "embedding_device": "cpu",
        "chroma_collection": "nist_ai_risk_corpus",
        "chroma_count": 447,
    }
