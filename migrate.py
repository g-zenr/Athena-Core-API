"""
Database migration script.
Run once to set up PostgreSQL tables, enable pgvector, and create the HNSW index.
Usage: .venv/Scripts/python migrate.py
"""
from sqlalchemy import text

from app.database import engine, Base
from app.models.document import Document  # noqa: registers model with Base
from app.models.chunk import Chunk        # noqa: registers model with Base


def migrate():
    print("Connecting to PostgreSQL...")

    with engine.connect() as conn:
        print("Enabling pgvector extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    print("Creating tables (documents, chunks)...")
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        print("Creating HNSW index on chunks.embedding (cosine ops)...")
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        ))
        conn.commit()

    print("\nMigration complete!")
    print("Tables  : documents, chunks")
    print("Index   : chunks_embedding_hnsw_idx (HNSW, cosine)")
    print("\nNext step: .venv/Scripts/python run.py")


if __name__ == "__main__":
    migrate()
