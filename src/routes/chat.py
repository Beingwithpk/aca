import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.config import SUPABASE_URL, SUPABASE_STORAGE_BUCKET
from src.db import get_connection
from src.models import ChatQueryRequest
from src.security import get_current_user
from src.services.embeddings import get_embedding
from src.services.llm import stream_rag_response

router = APIRouter(prefix="/api/chat", tags=["Chat"])


def build_public_pdf_url(storage_path: str, page_number: int | None = None) -> str:
    """Constructs a direct Supabase public object URL with an Adobe #page anchor."""
    base_url = SUPABASE_URL.rstrip("/")
    bucket = SUPABASE_STORAGE_BUCKET.strip("/")
    path = storage_path.lstrip("/")
    url = f"{base_url}/storage/v1/object/public/{bucket}/{path}"
    if page_number:
        url += f"#page={page_number}"
    return url


@router.post("/stream")
def query_academic_rag_stream(
    payload: ChatQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Streams RAG response using Server-Sent Events (SSE).
    Retrieves Top-5 relevant chunks joined with parent document metadata for direct PDF linking.
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

    # 2. Similarity search in pgvector with JOIN to documents table
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    dc.doc_type, 
                    dc.page_number, 
                    dc.content, 
                    1 - (dc.embedding <=> %s::vector) AS similarity,
                    d.filename,
                    d.storage_path
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.course_id = %s
                ORDER BY dc.embedding <=> %s::vector ASC
                LIMIT 5;
                """,
                (vector_str, clean_course_id, vector_str)
            )
            rows = cur.fetchall()

    if not rows:
        def empty_generator():
            msg = json.dumps({
                "type": "token",
                "data": f"No course materials found for subject '{clean_course_id}'. Please upload lecture notes or syllabi first."
            })
            yield f"data: {msg}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(empty_generator(), media_type="text/event-stream")

    sources = []
    for r in rows:
        page_num = r[1]
        storage_path = r[5] or ""
        pdf_url = build_public_pdf_url(storage_path, page_num) if storage_path else None

        sources.append({
            "doc_type": r[0] or "Document",
            "page_number": page_num,
            "content": r[2],
            "similarity": round(float(r[3]), 4),
            "filename": r[4] or "Document.pdf",
            "pdf_url": pdf_url
        })

    history = [m.model_dump() for m in payload.history] if payload.history else None

    # 3. Stream generator response
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
            "X-Accel-Buffering": "no"
        }
    )