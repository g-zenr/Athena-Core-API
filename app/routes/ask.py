"""
POST /api/ask        — Full response (waits for completion)
POST /api/ask/stream — Streaming response (words appear as generated)
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.dependencies.api_key import verify_api_key
from app.llm.model import llm
from app.rag.prompt_builder import NO_CONTEXT_RESPONSE, build_prompt, extract_citations
from app.rag.retriever import retriever

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ask"])


# --------------------------------------------------------------------------- #
# Shared schema
# --------------------------------------------------------------------------- #

class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The question to answer from the uploaded documents.",
        examples=["What are the key concepts covered in Chapter 3?"],
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of context chunks to retrieve (1-20).",
    )


# --------------------------------------------------------------------------- #
# Helper: retrieve + build prompt
# --------------------------------------------------------------------------- #

def _retrieve_and_build(question: str, top_k: int):
    """Shared retrieval logic for both endpoints."""
    try:
        chunks = retriever.search(question, k=top_k)
    except Exception as e:
        logger.error("Retriever search failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector search is unavailable. Upload a document first.",
        )

    if not chunks:
        return None, [], None

    prompt = build_prompt(question, chunks)
    citations = extract_citations(chunks)
    return prompt, citations, chunks


# --------------------------------------------------------------------------- #
# POST /api/ask  — full response
# --------------------------------------------------------------------------- #

@router.post("/ask", response_model=dict)
def ask_question(
    payload: AskRequest,
    _: str = Depends(verify_api_key),
):
    """Answer a question from uploaded documents. Waits for the full answer before returning."""
    question = payload.question.strip()
    prompt, citations, _ = _retrieve_and_build(question, payload.top_k)

    if prompt is None:
        return {"data": {"answer": NO_CONTEXT_RESPONSE, "citations": []}}

    try:
        answer = llm.generate(
            user_message=prompt["user"],
            system_prompt=prompt["system"],
        )
    except FileNotFoundError as e:
        logger.error("LLM model not found: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        logger.error("LLM generation failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM inference failed. Check server logs.",
        )

    return {"data": {"answer": answer or NO_CONTEXT_RESPONSE, "citations": citations}}


# --------------------------------------------------------------------------- #
# POST /api/ask/stream  — streaming response (SSE)
# --------------------------------------------------------------------------- #

@router.post("/ask/stream")
def ask_question_stream(
    payload: AskRequest,
    _: str = Depends(verify_api_key),
):
    """
    Answer a question with streaming.
    Returns Server-Sent Events — words appear as they are generated.

    Event format:
      data: {"token": "word"}    ← each generated token
      data: {"citations": [...]}  ← sent once at the end
      data: [DONE]                ← signals completion
    """
    question = payload.question.strip()
    prompt, citations, _ = _retrieve_and_build(question, payload.top_k)

    if prompt is None:
        def no_context():
            yield f"data: {json.dumps({'token': NO_CONTEXT_RESPONSE})}\n\n"
            yield f"data: {json.dumps({'citations': []})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_context(), media_type="text/event-stream")

    def token_stream():
        try:
            for token in llm.generate_stream(
                user_message=prompt["user"],
                system_prompt=prompt["system"],
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"

            yield f"data: {json.dumps({'citations': citations})}\n\n"
            yield "data: [DONE]\n\n"

        except FileNotFoundError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("Streaming LLM failed: %s", e, exc_info=True)
            yield f"data: {json.dumps({'error': 'LLM inference failed.'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")
