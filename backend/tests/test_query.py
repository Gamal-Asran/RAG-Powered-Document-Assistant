from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.tests.conftest import build_runtime


QUESTION = "What are the four core functions?"


def test_valid_query_returns_answer_sources_and_conversation(client):
    response = client.post("/query", json={"question": QUESTION})
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]
    assert payload["conversation_id"]
    assert len(payload["sources"]) == 4
    assert payload["status"] == "completed"


def test_blank_question_returns_422(client):
    response = client.post("/query", json={"question": "   "})
    assert response.status_code == 422


def test_thinking_disabled_is_empty(client):
    payload = client.post("/query", json={"question": QUESTION, "thinking_enabled": False}).json()
    assert payload["thinking"] == ""
    assert payload["thinking_enabled"] is False


def test_thinking_enabled_is_separate(client):
    payload = client.post("/query", json={"question": QUESTION, "thinking_enabled": True}).json()
    assert payload["thinking"] == "I used the retrieved framework evidence."
    assert payload["thinking"] not in payload["answer"]


def test_existing_conversation_receives_another_exchange(client):
    first = client.post("/query", json={"question": QUESTION}).json()
    second = client.post(
        "/query",
        json={"question": "How are they used?", "conversation_id": first["conversation_id"]},
    ).json()
    assert second["conversation_id"] == first["conversation_id"]
    conversation = client.get(f"/conversations/{first['conversation_id']}").json()
    assert len(conversation["messages"]) == 4


def test_ollama_unavailable_returns_503():
    runtime = build_runtime(available=False)
    app = create_app(settings=runtime.settings, runtime_loader=lambda _: runtime)
    with TestClient(app) as test_client:
        response = test_client.post("/query", json={"question": QUESTION})
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_generation_failure_returns_503():
    runtime = build_runtime(generation_fails=True)
    app = create_app(settings=runtime.settings, runtime_loader=lambda _: runtime)
    with TestClient(app) as test_client:
        response = test_client.post("/query", json={"question": QUESTION})
    assert response.status_code == 503


def test_source_metadata_contract(client):
    source = client.post("/query", json={"question": QUESTION}).json()["sources"][0]
    assert {"chunk_id", "document_id", "title", "page", "url", "similarity", "text_preview"} <= source.keys()
    assert source["chunk_id"] and source["title"] and source["url"]
