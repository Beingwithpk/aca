import io
import uuid
import traceback
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from pypdf import PdfReader

from src.db import get_connection
from src.models import DocumentOut
from src.security import get_current_user, require_role
from src.services.storage import upload_pdf_to_storage
from src.services.embeddings import get_embeddings_batch, chunk_text

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    course_id: str = Form(...),
    doc_type: str = Form(...),
    current_user: dict = Depends(require_role("admin", "faculty"))
):
    """Admin/Faculty: Upload a PDF, upload to Supabase Storage, and index chunks in pgvector."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported."
        )

    clean_course_id = course_id.strip().upper()

    # 1. Validate course exists
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM courses WHERE code = %s;", (clean_course_id,))
            if not cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Course '{clean_course_id}' does not exist."
                )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # 2. Upload to Supabase Storage
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    storage_path = f"{clean_course_id}/{doc_type}/{unique_filename}"
    try:
        upload_pdf_to_storage(file_bytes, storage_path)
    except Exception as e:
        print(f"[STORAGE WARNING] Cloud storage upload skipped/warning: {e}")

    # 3. Insert parent document row
    doc_id = str(uuid.uuid4())
    user_id = current_user.get("id")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (id, course_id, doc_type, filename, storage_path, uploaded_by)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (doc_id, clean_course_id, doc_type, file.filename, storage_path, user_id)
                )

            # 4. Extract PDF text and collect chunks with page metadata
            reader = PdfReader(io.BytesIO(file_bytes))
            raw_chunks_meta = []  # list of (chunk_text, page_number)

            for page_idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                text_chunks = chunk_text(page_text, chunk_size=400, overlap=40)
                for chunk in text_chunks:
                    raw_chunks_meta.append((chunk, page_idx + 1))

            chunk_records = []

            # 5. Generate embeddings via API in batches (16 chunks per batch)
            BATCH_SIZE = 16
            for i in range(0, len(raw_chunks_meta), BATCH_SIZE):
                batch = raw_chunks_meta[i:i + BATCH_SIZE]
                texts = [item[0] for item in batch]
                batch_vectors = get_embeddings_batch(texts)

                for (chunk, page_num), vector in zip(batch, batch_vectors):
                    vector_str = f"[{','.join(map(str, vector))}]"
                    chunk_records.append((
                        str(uuid.uuid4()),
                        doc_id,
                        clean_course_id,
                        doc_type,
                        chunk,
                        vector_str,
                        page_num
                    ))

            # 6. Bulk insert vector chunks
            if chunk_records:
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO document_chunks (
                            id, document_id, course_id, doc_type, content, embedding, page_number
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::vector, %s);
                        """,
                        chunk_records
                    )
            conn.commit()

        return {
            "message": "Document ingested and vectorized successfully",
            "document_id": doc_id,
            "filename": file.filename,
            "chunks_indexed": len(chunk_records)
        }

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(exc)}"
        )


@router.get("/{course_code}", response_model=List[DocumentOut])
def get_course_documents(
    course_code: str,
    current_user: dict = Depends(get_current_user)
):
    """Retrieve all uploaded documents for a specific course."""
    clean_code = course_code.strip().upper()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, course_id, doc_type, filename, storage_path, uploaded_by, created_at
                FROM documents
                WHERE course_id = %s
                ORDER BY created_at DESC;
                """,
                (clean_code,)
            )
            rows = cur.fetchall()

    return [
        {
            "id": str(r[0]),
            "course_id": r[1],
            "doc_type": r[2],
            "filename": r[3],
            "storage_path": r[4],
            "uploaded_by": str(r[5]) if r[5] else None,
            "created_at": r[6]
        }
        for r in rows
    ]