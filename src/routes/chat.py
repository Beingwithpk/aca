import json
import traceback
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.config import SUPABASE_URL, SUPABASE_STORAGE_BUCKET
from src.db import get_connection
from src.models import ChatQueryRequest, SamplePaperRequest
from src.security import get_current_user
from src.services.embeddings import get_embedding
from src.services.llm import stream_rag_response, get_llm_client, LLM_MODEL

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
        print(f"[CHAT ERROR] Embedding generation failed: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}"
        )

    # 2. Similarity search in pgvector with JOIN to documents table
    try:
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
    except Exception as e:
        print(f"[CHAT ERROR] Database pgvector query failed: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {str(e)}"
        )

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
            "content": r[2] or "",
            "similarity": round(float(r[3]), 4) if r[3] is not None else 0.0,
            "filename": r[4] or "Document.pdf",
            "pdf_url": pdf_url
        })

    history = [m.model_dump() for m in payload.history] if payload.history else None

    # 3. Stream generator response with safety try-catch
    def safe_stream_wrapper():
        try:
            for chunk in stream_rag_response(
                query=user_query,
                context_chunks=sources,
                conversation_history=history
            ):
                yield chunk
        except Exception as err:
            print(f"[CHAT ERROR] Streaming error during generation: {err}")
            traceback.print_exc()
            err_msg = json.dumps({"type": "error", "data": str(err)})
            yield f"data: {err_msg}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        safe_stream_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/generate-paper")
def generate_sample_paper(
    payload: SamplePaperRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Synthesizes a realistic academic question paper grounded in:
    1. Syllabus (coverage)
    2. Previous Year Questions (pattern and mark distribution)
    3. Lecture Notes (technical depth)
    """
    clean_course_id = payload.course_id.strip().upper()

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Fetch Syllabus chunks
                cur.execute(
                    """
                    SELECT content FROM document_chunks 
                    WHERE course_id = %s AND LOWER(doc_type) LIKE %s
                    LIMIT 4;
                    """,
                    (clean_course_id, "%syllabus%")
                )
                syllabus_rows = cur.fetchall()

                # 2. Fetch PYQ chunks
                cur.execute(
                    """
                    SELECT content FROM document_chunks 
                    WHERE course_id = %s AND LOWER(doc_type) LIKE %s
                    LIMIT 6;
                    """,
                    (clean_course_id, "%previous year%")
                )
                pyq_rows = cur.fetchall()

                # 3. Fetch Core Lecture / Reference chunks
                cur.execute(
                    """
                    SELECT content FROM document_chunks 
                    WHERE course_id = %s 
                      AND LOWER(doc_type) NOT LIKE %s 
                      AND LOWER(doc_type) NOT LIKE %s
                    ORDER BY created_at DESC
                    LIMIT 10;
                    """,
                    (clean_course_id, "%syllabus%", "%previous year%")
                )
                note_rows = cur.fetchall()
    except Exception as e:
        print(f"[PAPER ERROR] Database extraction failed: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch course materials: {str(e)}"
        )

    if not syllabus_rows and not pyq_rows and not note_rows:
        def empty_gen():
            msg = json.dumps({
                "type": "token",
                "data": f"Cannot generate a sample paper for {clean_course_id}. No course documents (syllabus, PYQs, or lecture notes) have been uploaded yet."
            })
            yield f"data: {msg}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_gen(), media_type="text/event-stream")

    syllabus_text = "\n---\n".join([r[0] for r in syllabus_rows if r[0]]) or "Follow standard university scope for this course code."
    pyq_text = "\n---\n".join([r[0] for r in pyq_rows if r[0]]) or "Standard examination pattern with Short and Long answer questions."
    notes_text = "\n---\n".join([r[0] for r in note_rows if r[0]]) or "General core concepts."

    system_prompt = (
        "You are an academic controller of examinations and senior university professor. "
        "Your task is to design an authentic, rigorous examination paper based strictly on the provided "
        "syllabus, recurring question styles from previous year questions (PYQs), and lecture materials.\n\n"
        "Rules:\n"
        "1. Strictly adhere to the requested total marks and exam type.\n"
        "2. Structure the paper cleanly with Sections (e.g., Section A: Concept & Definitions, Section B: Problem Solving & Derivations, Section C: Comprehensive Analysis).\n"
        "3. Provide exact mark breakdowns for each question (e.g., '[5 Marks]').\n"
        "4. Use standard LaTeX notation for mathematical equations, relations, and functional dependencies ($...$).\n"
        "5. If 'include_solutions' is True, append a detailed 'Marking Scheme & Model Answers' section at the end with step-by-step solutions."
    )

    user_prompt = f"""
Course Code: {clean_course_id}
Exam Type: {payload.exam_type}
Total Marks: {payload.total_marks}
Difficulty Level: {payload.difficulty}
Include Model Solutions: {payload.include_solutions}

=== SYLLABUS & MODULE SCOPE ===
{syllabus_text}

=== PREVIOUS YEAR QUESTION (PYQ) PATTERNS ===
{pyq_text}

=== REFERENCE COURSE CONTENT ===
{notes_text}

Generate the complete examination paper now.
"""

    def stream_paper():
        try:
            client = get_llm_client()
            stream = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2500,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    token = chunk.choices[0].delta.content or ""
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
        except Exception as e:
            print(f"[PAPER ERROR] LLM completion failure: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_paper(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )