from uuid import uuid4


def test_conversation_list_get_delete(client):
    created = client.post("/query", json={"question": "Explain the AI RMF functions."}).json()
    conversation_id = created["conversation_id"]
    listing = client.get("/conversations")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == conversation_id
    assert listing.json()[0]["message_count"] == 2
    fetched = client.get(f"/conversations/{conversation_id}")
    assert fetched.status_code == 200
    assert [message["role"] for message in fetched.json()["messages"]] == ["user", "assistant"]
    assert client.delete(f"/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/conversations/{conversation_id}").status_code == 404


def test_unknown_conversation_returns_404(client):
    assert client.get(f"/conversations/{uuid4()}").status_code == 404


def test_unknown_valid_uuid_query_creates_that_conversation(client):
    requested_id = str(uuid4())
    response = client.post("/query", json={"question": "What is the AI RMF?", "conversation_id": requested_id})
    assert response.status_code == 200
    assert response.json()["conversation_id"] == requested_id


def test_malformed_conversation_id_returns_404(client):
    response = client.post("/query", json={"question": "What is the AI RMF?", "conversation_id": "not-a-uuid"})
    assert response.status_code == 404
