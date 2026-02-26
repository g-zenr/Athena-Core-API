"""Tests for POST /api/ask and POST /api/ask/stream endpoints."""
import json


# ---------------------------------------------------------------------------
# /api/ask — full response
# ---------------------------------------------------------------------------

def test_ask_returns_answer(client, auth_headers):
    response = client.post(
        "/api/ask",
        json={"question": "What are the key concepts in Chapter 3?"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0


def test_ask_returns_citations(client, auth_headers):
    response = client.post(
        "/api/ask",
        json={"question": "What are the key concepts in Chapter 3?"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    citations = response.json()["data"]["citations"]
    assert isinstance(citations, list)
    assert len(citations) > 0
    assert "document" in citations[0]
    assert "section" in citations[0]


def test_ask_citation_matches_retrieved_chunk(client, auth_headers, mock_retriever):
    mock_retriever.search.return_value = [
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "document_title": "Introduction to Python Programming",
            "year": 2023,
            "section": "Chapter 3",
            "text": "Chapter 3 covers functions and scope...",
            "score": 0.92,
        }
    ]
    response = client.post(
        "/api/ask",
        json={"question": "What does Chapter 3 cover?"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    citations = response.json()["data"]["citations"]
    assert citations[0]["document"] == "Introduction to Python Programming"
    assert citations[0]["section"] == "Chapter 3"


def test_ask_deduplicates_citations(client, auth_headers, mock_retriever):
    """Multiple chunks from the same section should appear once in citations."""
    mock_retriever.search.return_value = [
        {"id": "c1", "document_id": "d1", "document_title": "Doc A",
         "year": 2023, "section": "Chapter 1", "text": "text 1", "score": 0.9},
        {"id": "c2", "document_id": "d1", "document_title": "Doc A",
         "year": 2023, "section": "Chapter 1", "text": "text 2", "score": 0.85},
    ]
    response = client.post(
        "/api/ask",
        json={"question": "Tell me about Chapter 1"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    citations = response.json()["data"]["citations"]
    assert len(citations) == 1
    assert citations[0]["document"] == "Doc A"
    assert citations[0]["section"] == "Chapter 1"


def test_ask_no_results_returns_fallback(client, auth_headers, mock_retriever):
    """When the retriever returns no chunks the fallback message is returned."""
    mock_retriever.search.return_value = []
    response = client.post(
        "/api/ask",
        json={"question": "What is a topic not in any document?"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "not available" in data["answer"].lower()
    assert data["citations"] == []


def test_ask_requires_api_key(client):
    response = client.post(
        "/api/ask",
        json={"question": "What is covered in Chapter 3?"},
    )
    assert response.status_code == 403


def test_ask_invalid_api_key(client):
    response = client.post(
        "/api/ask",
        json={"question": "What is covered in Chapter 3?"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 403


def test_ask_question_too_short(client, auth_headers):
    response = client.post(
        "/api/ask",
        json={"question": "Hi"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_ask_missing_question(client, auth_headers):
    response = client.post("/api/ask", json={}, headers=auth_headers)
    assert response.status_code == 422


def test_ask_custom_top_k(client, auth_headers, mock_retriever):
    client.post(
        "/api/ask",
        json={"question": "What is covered in the curriculum?", "top_k": 5},
        headers=auth_headers,
    )
    mock_retriever.search.assert_called_once_with(
        "What is covered in the curriculum?", k=5
    )


# ---------------------------------------------------------------------------
# /api/ask/stream — Server-Sent Events
# ---------------------------------------------------------------------------

def test_ask_stream_returns_200(client, auth_headers):
    response = client.post(
        "/api/ask/stream",
        json={"question": "What is covered in Chapter 3?"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_ask_stream_emits_tokens_and_done(client, auth_headers, mock_llm):
    mock_llm.generate_stream.return_value = iter(["Chapter", " 3", " explains", "."])

    response = client.post(
        "/api/ask/stream",
        json={"question": "What is covered in Chapter 3?"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    raw = response.text
    events = [line for line in raw.split("\n") if line.startswith("data:")]

    # Must contain at least one token event
    token_events = [e for e in events if '"token"' in e]
    assert len(token_events) > 0, "No token events in stream"

    # Must contain exactly one citations event
    citation_events = [e for e in events if '"citations"' in e]
    assert len(citation_events) == 1, "Expected exactly one citations event"

    # Must end with [DONE]
    assert any(e.strip() == "data: [DONE]" for e in events), "Missing [DONE] terminator"


def test_ask_stream_no_results_returns_fallback(client, auth_headers, mock_retriever):
    """When retriever finds nothing the stream should still complete cleanly."""
    mock_retriever.search.return_value = []

    response = client.post(
        "/api/ask/stream",
        json={"question": "Topic not in any document?"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    raw = response.text
    assert "not available" in raw.lower()
    assert "data: [DONE]" in raw


def test_ask_stream_requires_api_key(client):
    response = client.post(
        "/api/ask/stream",
        json={"question": "What is in Chapter 3?"},
    )
    assert response.status_code == 403
