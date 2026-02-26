"""
Pytest fixtures for Athena Core API.
Mocks the LLM, embedder, pgvector retriever, and storage so tests
never touch the real model files or the PostgreSQL database.
"""
import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key-12345"


# ---------------------------------------------------------------------------
# Environment setup (must happen before the app module is imported)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def set_env():
    os.environ.setdefault("API_KEY", TEST_API_KEY)
    os.environ.setdefault("MODEL_PATH", "models/test.gguf")
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")


# ---------------------------------------------------------------------------
# Temporary directories
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def tmp_dirs(tmp_path, monkeypatch):
    """Redirect DATA_DIR and UPLOAD_DIR to a temp path for each test."""
    (tmp_path / "data").mkdir()
    (tmp_path / "uploads").mkdir()
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    return tmp_path


# ---------------------------------------------------------------------------
# Retriever mock
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_retriever():
    """Mock the pgvector retriever singleton."""
    with patch("app.rag.retriever.retriever") as mock:
        mock.search.return_value = [
            {
                "id": "chunk-uuid-1",
                "document_id": "doc-uuid-1",
                "document_title": "Introduction to Python Programming",
                "year": 2023,
                "section": "Chapter 3",
                "text": (
                    "Chapter 3 covers functions and scope. "
                    "A function is a reusable block of code that performs a specific task."
                ),
                "score": 0.92,
            }
        ]
        mock.add_chunks.return_value = None
        mock.rebuild.return_value = None
        mock.is_loaded = True
        mock.size = 1
        mock.load.return_value = True
        yield mock


# ---------------------------------------------------------------------------
# LLM mock
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_llm():
    """Mock the LLM singleton."""
    with patch("app.llm.model.llm") as mock:
        mock.generate.return_value = (
            "Chapter 3 explains functions and variable scope in Python programming."
        )
        mock.generate_stream.return_value = iter(
            ["Chapter", " 3", " explains", " functions", "."]
        )
        mock.is_loaded = True
        yield mock


# ---------------------------------------------------------------------------
# Embedder mock
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_embedder():
    """
    Mock the embedder singleton.

    encode()        → (n, 384) float32 array  — used when embedding a batch
    encode_single() → (1, 384) float32 array  — used during retrieval; caller does [0]
    embedding_dim   → 384                      — validated against EMBEDDING_DIM at startup
    """
    with patch("app.rag.embedder.embedder") as mock:
        mock.encode.return_value = np.ones((1, 384), dtype=np.float32)
        mock.encode_single.return_value = np.ones((1, 384), dtype=np.float32)
        mock.embedding_dim = 384
        mock.is_loaded = True
        yield mock


# ---------------------------------------------------------------------------
# Storage mock (bypasses real PostgreSQL)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def mock_storage(tmp_dirs):
    """Patch settings.DATA_DIR so storage functions use the temp path."""
    with patch("app.storage.metadata_store.settings") as ms, \
         patch("app.storage.chunk_store.settings") as cs:
        ms.DATA_DIR = str(tmp_dirs / "data")
        cs.DATA_DIR = str(tmp_dirs / "data")
        yield


# ---------------------------------------------------------------------------
# Test client
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client(mock_retriever, mock_llm, mock_embedder, mock_storage):
    """
    FastAPI TestClient with all external dependencies mocked.

    The lifespan patches:
      - create_tables  → no-op  (avoids real DB connection)
      - retriever      → mock   (avoids real pgvector search)
      - llm            → mock   (avoids real model loading)

    The embedder is already patched by the mock_embedder fixture, so the
    startup dimension validation will compare 384 == 384 and pass.
    """
    with patch("app.database.create_tables"), \
         patch("app.rag.retriever.retriever", mock_retriever), \
         patch("app.llm.model.llm", mock_llm):
        from app.main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture(scope="function")
def auth_headers():
    return {"X-API-Key": TEST_API_KEY}
