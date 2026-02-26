import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: create DB tables + HNSW index, validate embedding dimension,
    ensure upload directory exists.
    LLM and embedder are lazy-loaded on first request.
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    from app.database import create_tables
    create_tables()

    # Validate that the live embedding model's output dimension matches
    # the Vector(dim) column declared in the Chunk model.
    # Catches mismatches early instead of failing silently at index time.
    from app.models.chunk import EMBEDDING_DIM
    from app.rag.embedder import embedder
    actual_dim = embedder.embedding_dim
    if actual_dim != EMBEDDING_DIM:
        raise RuntimeError(
            f"Embedding dimension mismatch: model '{settings.EMBEDDING_MODEL}' produces "
            f"{actual_dim}-dim vectors, but the Chunk schema expects {EMBEDDING_DIM}. "
            "Update EMBEDDING_DIM in app/models/chunk.py or change EMBEDDING_MODEL in .env."
        )
    logger.info("Embedding dimension validated: %d", actual_dim)

    yield


app = FastAPI(
    title="Document Q&A AI Assistant",
    description=(
        "On-premise RAG-based AI that answers questions from your uploaded documents. "
        "Works for any domain: education, law, research, corporate, medical, and more."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to known origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Late imports to avoid circular dependency issues
from app.routes import ask, health, upload  # noqa: E402

app.include_router(ask.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(health.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Document Q&A AI Assistant", "docs": "/docs"}
