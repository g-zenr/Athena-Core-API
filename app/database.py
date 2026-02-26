"""
SQLAlchemy engine, session factory, and base model for PostgreSQL + pgvector.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # reconnect if connection dropped
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for a SQLAlchemy session.
    Rolls back automatically on exception; always closes the session.

    Usage:
        with get_db() as db:
            db.add(obj)
            db.commit()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables, enable pgvector extension, and create the HNSW index."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(bind=engine)

    # HNSW index for fast approximate nearest-neighbour search.
    # Uses cosine distance to match the retriever's cosine_distance() ordering.
    # HNSW does not require pre-existing rows (unlike IVFFLAT).
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        ))
        conn.commit()


def check_connection() -> bool:
    """Returns True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
