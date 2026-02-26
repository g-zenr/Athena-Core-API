"""
GET /api/health — System health check.
"""
from fastapi import APIRouter

from app.database import check_connection
from app.llm.model import llm
from app.rag.retriever import retriever
from app.storage.chunk_store import count_chunks

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Returns server health and database status."""
    db_ok = check_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "model_loaded": llm.is_loaded,
        "total_chunks": count_chunks() if db_ok else 0,
        "indexed_chunks": retriever.size if db_ok else 0,
    }
