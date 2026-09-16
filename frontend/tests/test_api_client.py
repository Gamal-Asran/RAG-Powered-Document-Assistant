from __future__ import annotations

import httpx
import pytest

from frontend.api_client import (
    BackendClient,
    BackendTimeoutError,
    BackendUnavailableError,
    BackendValidationError,
)


SOURCE = {
    "chunk_id": "nist_ai_rmf_1_0-p0024-c000",
    "document_id": "nist_ai_rmf_1_0",
    "title": "Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
    "page": 24,
    "url": "https://nvlpubs.nist.gov/example.pdf",
    "similarity": 0.7314,
    "text_preview": "The Framework Core contains four functions.",
}

QUERY_RESPONSE = {
    "conversation_id": "fa6d23ea-1238-45ca-a79c-c1157e1a06ea",
    "answer": "The functions are GOVERN, MAP, MEASURE, and MANAGE.",
    "thinking": "I matched the retrieved passage to the question.",
    "thinking_enabled": True,
    "sources": [SOURCE],
    "status": "completed",
    "retrieval_seconds": 0.12,
    "generation_seconds": 18.4,
}

SUMMARY = {
    "id": QUERY_RESPONSE["conversation_id"],
    "title": "What are the four core functions?",
    "created_at": "2026-09-16T12:00:00Z",
    "updated_at": "2026-09-16T12:01:00Z",
    "message_count": 2,
}


def client_for(handler) -> BackendClient:
    return BackendClient("http://testserver", transport=httpx.MockTransport(handler))


def test_health_response_parsing() -> None:
    payload = {
        "status": "healthy",
        "ollama": "available",
        "ollama_model": "qwen3:4b",
        "embedding_device": "cpu",
        "chroma_collection": "nist_ai_risk_corpus",
        "chroma_count": 447,
    }
    client = client_for(lambda request: httpx.Response(200, json=payload))

    health = client.health()

    assert health.status == "healthy"
    assert health.chroma_count == 447


def test_successful_query_parsing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/query"
        return httpx.Response(200, json=QUERY_RESPONSE)

    response = client_for(handler).query("What are the functions?", None, True)

    assert response.answer == "The functions are GOVERN, MAP, MEASURE, and MANAGE."
    assert response.thinking == "I matched the retrieved passage to the question."


def test_answer_and_thinking_remain_separate() -> None:
    response = client_for(lambda request: httpx.Response(200, json=QUERY_RESPONSE)).query(
        "What are the functions?", None, True
    )

    assert response.thinking not in response.answer


def test_thinking_disabled_accepts_empty_thinking() -> None:
    payload = {**QUERY_RESPONSE, "thinking": "", "thinking_enabled": False}
    response = client_for(lambda request: httpx.Response(200, json=payload)).query(
        "What are the functions?", None, False
    )

    assert response.thinking == ""
    assert response.thinking_enabled is False


def test_source_metadata_parsing() -> None:
    response = client_for(lambda request: httpx.Response(200, json=QUERY_RESPONSE)).query(
        "What are the functions?", None, True
    )

    source = response.sources[0]
    assert source.chunk_id == "nist_ai_rmf_1_0-p0024-c000"
    assert source.document_id == "nist_ai_rmf_1_0"
    assert source.page == 24
    assert source.similarity == pytest.approx(0.7314)


def test_conversation_list_parsing() -> None:
    conversations = client_for(lambda request: httpx.Response(200, json=[SUMMARY])).list_conversations()

    assert len(conversations) == 1
    assert conversations[0].message_count == 2


def test_conversation_retrieval() -> None:
    payload = {
        **SUMMARY,
        "messages": [
            {
                "id": "m1",
                "role": "user",
                "content": "What are the functions?",
                "thinking": "",
                "sources": [],
                "created_at": "2026-09-16T12:00:00Z",
            },
            {
                "id": "m2",
                "role": "assistant",
                "content": QUERY_RESPONSE["answer"],
                "thinking": QUERY_RESPONSE["thinking"],
                "sources": [SOURCE],
                "created_at": "2026-09-16T12:01:00Z",
            },
        ],
    }
    conversation = client_for(lambda request: httpx.Response(200, json=payload)).get_conversation(
        SUMMARY["id"]
    )

    assert [message.role for message in conversation.messages] == ["user", "assistant"]
    assert conversation.messages[1].sources[0].page == 24


def test_conversation_deletion() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(204)

    client_for(handler).delete_conversation(SUMMARY["id"])

    assert seen == [("DELETE", f"/conversations/{SUMMARY['id']}")]


def test_backend_connection_failure_has_specific_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(BackendUnavailableError):
        client_for(handler).list_conversations()


def test_query_timeout_has_specific_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(BackendTimeoutError):
        client_for(handler).query("What are the functions?", None, False)


def test_invalid_backend_response_is_rejected() -> None:
    invalid = {**QUERY_RESPONSE}
    invalid.pop("answer")

    with pytest.raises(BackendValidationError):
        client_for(lambda request: httpx.Response(200, json=invalid)).query(
            "What are the functions?", None, False
        )
