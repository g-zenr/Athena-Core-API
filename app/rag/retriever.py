"""
pgvector-based retriever for document chunks.
Embeddings are stored persistently in the chunks table.
Uses HNSW index for fast approximate nearest-neighbour cosine search.
"""
from typing import Optional

from sqlalchemy import update

from app.database import get_db
from app.models.chunk import Chunk


class PGVectorRetriever:
    """
    Retrieves relevant chunks using pgvector cosine similarity search.
    No in-memory index — search runs directly against PostgreSQL via HNSW.
    """

    _instance: Optional["PGVectorRetriever"] = None

    def __new__(cls) -> "PGVectorRetriever":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> bool:
        """No-op: pgvector data persists in PostgreSQL, nothing to load."""
        return True

    def add_chunks(self, chunks: list[dict]) -> None:
        """
        Embed chunk texts and persist the vectors in PostgreSQL.
        Called after chunk_store.add_chunks() inserts the rows.

        Uses bulk ORM attribute assignment so the Vector type adapter
        (process_bind_param) is always invoked correctly.
        """
        if not chunks:
            return

        from app.rag.embedder import embedder

        texts = [c["text"] for c in chunks]
        embeddings = embedder.encode(texts)  # shape: (n, embedding_dim), float32

        with get_db() as db:
            for i, chunk in enumerate(chunks):
                db.execute(
                    update(Chunk)
                    .where(Chunk.id == chunk["id"])
                    .values(embedding=embeddings[i].tolist())
                )
            db.commit()

    def rebuild(self) -> None:
        """
        No-op: pgvector stores embeddings persistently in PostgreSQL.
        Deletions cascade automatically via the FK constraint.
        """
        pass

    def search(self, query_text: str, k: int = 5) -> list[dict]:
        """
        Find the k most similar chunks using cosine similarity.

        Returns chunk dicts ordered by relevance (highest similarity first).
        Each dict includes a ``score`` field in [0, 1] where 1 = identical.
        """
        from app.rag.embedder import embedder

        query_vec = embedder.encode_single(query_text)[0].tolist()
        distance_col = Chunk.embedding.cosine_distance(query_vec).label("distance")

        with get_db() as db:
            rows = (
                db.query(Chunk, distance_col)
                .filter(Chunk.embedding.is_not(None))
                .order_by(distance_col)
                .limit(k)
                .all()
            )
            return [
                {
                    "id": str(chunk.id),
                    "document_id": str(chunk.document_id),
                    "document_title": chunk.document_title,
                    "year": chunk.year,
                    "section": chunk.section,
                    "text": chunk.text,
                    # cosine_distance ∈ [0, 2]; convert to similarity ∈ [-1, 1]
                    # then clamp to [0, 1] for practical use
                    "score": round(max(0.0, 1.0 - float(distance)), 4),
                }
                for chunk, distance in rows
            ]

    @property
    def size(self) -> int:
        """Number of chunks that have embeddings stored."""
        with get_db() as db:
            return db.query(Chunk).filter(Chunk.embedding.is_not(None)).count()

    @property
    def is_loaded(self) -> bool:
        """Always True — pgvector is available as long as PostgreSQL is connected."""
        from app.database import check_connection
        return check_connection()


# Module-level singleton
retriever = PGVectorRetriever()
