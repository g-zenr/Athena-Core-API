"""Tests for document admin endpoints: upload, list, delete, health."""
import io
from unittest.mock import patch


def test_list_documents_empty(client, auth_headers):
    with patch("app.routes.upload.get_all_documents", return_value=[]):
        response = client.get("/api/documents", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_list_documents_requires_api_key(client):
    response = client.get("/api/documents")
    assert response.status_code == 403


def test_health_check_no_auth(client):
    """Health check must be accessible without authentication."""
    with patch("app.routes.health.check_connection", return_value=True), \
         patch("app.routes.health.count_chunks", return_value=0):
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "model_loaded" in body
    assert "total_chunks" in body
    assert "indexed_chunks" in body


def test_upload_document_txt(client, auth_headers):
    """Upload a .txt file and verify the response shape."""
    txt_content = b"""Chapter 1. Introduction to Learning
This chapter introduces the fundamentals of learning and cognition.

Chapter 2. Memory and Retention
This chapter explores how memory works and strategies for better retention."""

    with patch("app.routes.upload.process_document") as mock_proc, \
         patch("app.routes.upload.add_document") as mock_add_doc, \
         patch("app.routes.upload.add_chunks") as mock_add_chunks, \
         patch("app.routes.upload.retriever") as mock_ret:

        mock_proc.return_value = {
            "chunks": [
                {"section_label": "Chapter 1", "text": "Chapter 1. Introduction to Learning..."},
                {"section_label": "Chapter 2", "text": "Chapter 2. Memory and Retention..."},
            ],
            "chunk_count": 2,
            "strategy": "sections",
        }
        mock_add_doc.return_value = {
            "id": "doc-uuid-123",
            "title": "Fundamentals of Learning",
            "year": 2023,
            "section_count": 2,
            "created_at": "2024-01-01T00:00:00",
        }
        mock_add_chunks.return_value = [
            {"id": "chunk-1", "document_id": "doc-uuid-123",
             "document_title": "Fundamentals of Learning",
             "year": 2023, "section": "Chapter 1", "text": "Chapter 1..."},
            {"id": "chunk-2", "document_id": "doc-uuid-123",
             "document_title": "Fundamentals of Learning",
             "year": 2023, "section": "Chapter 2", "text": "Chapter 2..."},
        ]
        mock_ret.add_chunks.return_value = None

        response = client.post(
            "/api/upload-document",
            files={"file": ("learning.txt", io.BytesIO(txt_content), "text/plain")},
            data={"title": "Fundamentals of Learning", "year": "2023"},
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Fundamentals of Learning"
    assert data["chunks_indexed"] == 2
    assert "id" in data
    assert data["strategy"] == "sections"


def test_upload_unsupported_file_type(client, auth_headers):
    response = client.post(
        "/api/upload-document",
        files={"file": ("doc.docx", io.BytesIO(b"data"), "application/octet-stream")},
        data={"title": "Test Document", "year": "2020"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_requires_api_key(client):
    response = client.post(
        "/api/upload-document",
        files={"file": ("doc.txt", io.BytesIO(b"content"), "text/plain")},
        data={"title": "Test Document", "year": "2020"},
    )
    assert response.status_code == 403


def test_upload_rollback_on_indexing_failure(client, auth_headers):
    """If embedding/indexing fails the document record must be deleted."""
    with patch("app.routes.upload.process_document") as mock_proc, \
         patch("app.routes.upload.add_document") as mock_add_doc, \
         patch("app.routes.upload.add_chunks") as mock_add_chunks, \
         patch("app.routes.upload.delete_document") as mock_del_doc, \
         patch("app.routes.upload.retriever") as mock_ret:

        mock_proc.return_value = {
            "chunks": [{"section_label": "Chapter 1", "text": "Some text here."}],
            "chunk_count": 1,
            "strategy": "sections",
        }
        mock_add_doc.return_value = {"id": "doc-uuid-rollback", "title": "Bad Doc",
                                      "year": 2020, "section_count": 1,
                                      "created_at": "2024-01-01T00:00:00"}
        mock_add_chunks.side_effect = RuntimeError("DB write failed")

        response = client.post(
            "/api/upload-document",
            files={"file": ("bad.txt", io.BytesIO(b"Some text here."), "text/plain")},
            data={"title": "Bad Doc", "year": "2020"},
            headers=auth_headers,
        )

    assert response.status_code == 500
    mock_del_doc.assert_called_once_with("doc-uuid-rollback")


def test_delete_document_not_found(client, auth_headers):
    with patch("app.routes.upload.get_document", return_value=None):
        response = client.delete("/api/document/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."


def test_delete_document_requires_api_key(client):
    response = client.delete("/api/document/some-id")
    assert response.status_code == 403


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Document Q&A" in response.json()["message"]
