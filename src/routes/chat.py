import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.db import get_connection
from src.models import ChatQueryRequest
from src.security import get_current_user
from src.services.embeddings import get_embedding
from src.services.llm import stream_rag_response

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/stream")
def query_academic_rag_stream(
    payload: ChatQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Streams RAG response using Server-Sent Events (SSE).
    Retrieves Top-5 relevant chunks via pgvector, then yields tokens as they are generated.
    """
    clean_course_id = payload.course_id.strip().upper()
    user_query = payload.query.strip()

    if not user_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty."
        )

    # 1. Embed query
    try:
        query_vector = get_embedding(user_query)
        vector_str = f"[{','.join(map(str, query_vector))}]"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}"
        )

    # 2. Similarity search in pgvector
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    doc_type, 
                    page_number, 
                    content, 
                    1 - (embedding <=> %s::vector) AS similarity
                FROM document_chunks
                WHERE course_id = %s
                ORDER BY embedding <=> %s::vector ASC
                LIMIT 5;
                """,
                (vector_str, clean_course_id, vector_str)
            )
            rows = cur.fetchall()

    if not rows:
        # Return an SSE stream with an immediate empty message
        def empty_generator():
            msg = json.dumps({
                "type": "token",
                "data": f"No course materials found for subject '{clean_course_id}'. Please upload lecture notes or syllabi first."
            })
            yield f"data: {msg}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(empty_generator(), media_type="text/event-stream")

    sources = [
        {
            "doc_type": r[0],
            "page_number": r[1],
            "content": r[2],
            "similarity": round(float(r[3]), 4)
        }
        for r in rows
    ]

    history = [m.model_dump() for m in payload.history] if payload.history else None

    # 3. Return StreamingResponse wrapping our generator
    return StreamingResponse(
        stream_rag_response(
            query=user_query,
            context_chunks=sources,
            conversation_history=history
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Prevents Nginx/proxies from buffering chunks
        }
    )