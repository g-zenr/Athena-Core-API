"""
RAG prompt construction for the Document Q&A Assistant.
Builds a strict instruction prompt that forces the LLM to answer
ONLY from retrieved context, never from its training data.
Works for any domain: education, law, medicine, corporate, research, etc.
"""

NO_CONTEXT_RESPONSE = (
    "The requested information is not available in the provided documents. "
    "Please upload the relevant document to get an accurate answer."
)

SYSTEM_PROMPT = """You are a document research assistant. Your role is to answer questions accurately and strictly based on the provided document excerpts below.

STRICT RULES:
1. Answer ONLY using the information in the provided context sections.
2. Do NOT use your training knowledge or make assumptions beyond the context.
3. Always cite the specific document and section you are referencing.
4. If the context does not contain the answer, respond EXACTLY with: "The requested information is not available in the provided documents."
5. Be precise, clear, and professional in your language.
6. Do not add opinions, interpretations, or information not explicitly in the context."""


def build_prompt(question: str, chunks: list[dict]) -> dict | None:
    """
    Build the LLM prompt from a question and retrieved chunks.

    Args:
        question: The user's question.
        chunks: List of retrieved chunk dicts from the retriever.
                Each must have: document_title, section, text.

    Returns:
        Dict with keys "system" and "user" ready for chat-template inference,
        or None if no chunks are provided (caller should return fallback).
    """
    if not chunks:
        return None  # Caller should use NO_CONTEXT_RESPONSE directly

    # Build context block from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        document_title = chunk.get("document_title", "Unknown Document")
        section = chunk.get("section", "Unknown Section")
        text = chunk.get("text", "").strip()

        context_parts.append(
            f"[Context {i}]\n"
            f"Document: {document_title}\n"
            f"Section: {section}\n"
            f"Text:\n{text}"
        )

    context_block = "\n\n---\n\n".join(context_parts)

    user_message = (
        f"DOCUMENT CONTEXT:\n\n{context_block}\n\n"
        f"QUESTION: {question}"
    )

    return {"system": SYSTEM_PROMPT, "user": user_message}


def extract_citations(chunks: list[dict]) -> list[dict]:
    """
    Extract citation metadata from retrieved chunks.
    Returns a deduplicated list of {document, section} dicts.
    """
    seen = set()
    citations = []

    for chunk in chunks:
        document = chunk.get("document_title", "Unknown Document")
        section = chunk.get("section", "Unknown Section")
        key = (document, section)

        if key not in seen:
            seen.add(key)
            citations.append({"document": document, "section": section})

    return citations
