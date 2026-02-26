"""
PostgreSQL-based persistence for document metadata.
"""
import uuid
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.document import Document


def _to_dict(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "year": doc.year,
        "section_count": doc.section_count,
        "created_at": doc.created_at.isoformat(),
    }


def add_document(title: str, year: int, section_count: int) -> dict:
    """Insert a new document record and return the created record."""
    with get_db() as db:
        doc = Document(
            id=uuid.uuid4(),
            title=title,
            year=year,
            section_count=section_count,
            created_at=datetime.utcnow(),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return _to_dict(doc)


def get_all_documents() -> list[dict]:
    """Return all document records ordered by most recent first."""
    with get_db() as db:
        docs = db.query(Document).order_by(Document.created_at.desc()).all()
        return [_to_dict(d) for d in docs]


def get_document(document_id: str) -> Optional[dict]:
    """Return a single document record or None."""
    with get_db() as db:
        doc = db.query(Document).filter(Document.id == document_id).first()
        return _to_dict(doc) if doc else None


def delete_document(document_id: str) -> bool:
    """Delete a document record. Returns True if deleted, False if not found."""
    with get_db() as db:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return False
        db.delete(doc)
        db.commit()
        return True


def document_exists(document_id: str) -> bool:
    with get_db() as db:
        return db.query(Document).filter(Document.id == document_id).count() > 0
