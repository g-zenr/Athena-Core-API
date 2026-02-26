"""
PostgreSQL-based persistence for text chunks.
Chunks are stored with their embeddings in the chunks table (pgvector).
"""
import uuid
from typing import Optional

from app.database import get_db
from app.models.chunk import Chunk


def _to_dict(chunk: Chunk) -> dict:
    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "document_title": chunk.document_title,
        "year": chunk.year,
        "section": chunk.section,
        "text": chunk.text,
    }


def add_chunks(document_id: str, document_title: str, year: int, sections: list[dict]) -> list[dict]:
    """
    Insert chunks for a document (embeddings are added later by the retriever).

    Args:
        document_id:    UUID of the parent document.
        document_title: Denormalized title for fast retrieval.
        year:           Publication year.
        sections:       List of dicts with keys ``section_label`` and ``text``.

    Returns:
        List of persisted chunk dicts.

    Raises:
        ValueError: If any section has empty text.
    """
    for i, section in enumerate(sections):
        text = section.get("text", "").strip()
        if not text:
            raise ValueError(
                f"Section {section.get('section_label', i + 1)!r} has no text content."
            )

    with get_db() as db:
        new_chunks = []
        for i, section in enumerate(sections):
            chunk = Chunk(
                id=uuid.uuid4(),
                document_id=document_id,
                document_title=document_title,
                year=year,
                section=section.get("section_label", f"Section {i + 1}"),
                text=section["text"].strip(),
                embedding=None,
            )
            db.add(chunk)
            new_chunks.append(chunk)

        db.commit()
        return [_to_dict(c) for c in new_chunks]


def get_all_chunks() -> list[dict]:
    """Return all chunks (without embeddings)."""
    with get_db() as db:
        return [_to_dict(c) for c in db.query(Chunk).all()]


def get_chunks_by_document(document_id: str) -> list[dict]:
    """Return all chunks for a given document."""
    with get_db() as db:
        chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
        return [_to_dict(c) for c in chunks]


def delete_chunks_by_document(document_id: str) -> int:
    """
    Remove all chunks for a document.
    Returns the count of removed chunks.
    pgvector uses UUIDs — no re-numbering required.
    """
    with get_db() as db:
        count = db.query(Chunk).filter(Chunk.document_id == document_id).count()
        db.query(Chunk).filter(Chunk.document_id == document_id).delete()
        db.commit()
        return count


def count_chunks() -> int:
    with get_db() as db:
        return db.query(Chunk).count()
