"""
Document admin endpoints:
  POST   /api/upload-document  — Upload and index a document
  GET    /api/documents         — List all indexed documents
  DELETE /api/document/{id}    — Remove a document and all its chunks
"""
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.dependencies.api_key import verify_api_key
from app.rag.retriever import retriever
from app.services.document_processor import process_document
from app.storage.chunk_store import add_chunks, delete_chunks_by_document
from app.storage.metadata_store import (
    add_document,
    delete_document,
    get_all_documents,
    get_document,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".text"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


# --------------------------------------------------------------------------- #
# POST /api/upload-document
# --------------------------------------------------------------------------- #

@router.post("/upload-document", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(..., description="PDF or TXT document"),
    title: str = Form(..., min_length=2, max_length=200, description="Title of the document"),
    year: int = Form(..., ge=1900, le=2100, description="Year of publication or creation"),
    _: str = Depends(verify_api_key),
):
    """
    Upload a document (PDF or TXT), extract and chunk text,
    embed the chunks, and store them in the vector database.
    The entire pipeline is atomic: if embedding or indexing fails the
    document record is removed so the database stays consistent.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit.")

    # Persist the file so document_processor can open it
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    unique_filename = f"{uuid.uuid4().hex}{suffix}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # --- Text extraction & chunking ---
    try:
        result = process_document(file_path, title, year)
    except ValueError as exc:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        os.remove(file_path)
        logger.error("Document processing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process document.")

    chunks = result["chunks"]
    if not chunks:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="No content could be extracted from the document.")

    # --- Persist metadata ---
    doc_record = add_document(title, year, len(chunks))
    document_id = doc_record["id"]

    # --- Persist chunks + embed (atomic: roll back document on failure) ---
    try:
        stored_chunks = add_chunks(document_id, title, year, chunks)
        retriever.add_chunks(stored_chunks)
    except Exception as exc:
        logger.error("Upload pipeline failed for document %s: %s", document_id, exc, exc_info=True)
        # Clean up: removing the document cascades to any partial chunks via FK
        try:
            delete_document(document_id)
        except Exception:
            logger.warning("Failed to clean up document %s after pipeline error", document_id)
        raise HTTPException(
            status_code=500,
            detail="Document upload failed during indexing. Please try again.",
        )

    return {
        "data": {
            "id": document_id,
            "title": title,
            "year": year,
            "chunks_indexed": len(chunks),
            "strategy": result.get("strategy", "unknown"),
        }
    }


# --------------------------------------------------------------------------- #
# GET /api/documents
# --------------------------------------------------------------------------- #

@router.get("/documents")
def list_documents(_: str = Depends(verify_api_key)):
    """Return all indexed documents."""
    return {"data": get_all_documents()}


# --------------------------------------------------------------------------- #
# DELETE /api/document/{document_id}
# --------------------------------------------------------------------------- #

@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(document_id: str, _: str = Depends(verify_api_key)):
    """Delete a document and all its chunks (cascade via FK)."""
    if not get_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")

    delete_chunks_by_document(document_id)
    delete_document(document_id)

    # No-op for pgvector (embeddings live in the DB and cascade with the FK),
    # but kept for interface compatibility should the retriever backend change.
    try:
        retriever.rebuild()
    except Exception as exc:
        logger.error("Retriever rebuild failed after deletion: %s", exc, exc_info=True)
