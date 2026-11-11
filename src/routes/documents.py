import io
import uuid
import json
import traceback
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from pypdf import PdfReader

from src.db import get_connection
from src.models import DocumentOut
from src.security import get_current_user, require_role
from src.services.storage import upload_pdf_to_storage
from src.services.embeddings import get_embeddings_batch, chunk_text
from src.services.classifier import classify_document_and_subject, sanitize_text

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/predict")
async def predict_documents_metadata(
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(require_role("admin", "faculty"))
):
    """Inspects files and predicts Subject Code and Document Type without ingesting them."""
    # Retrieve enrolled courses
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, title FROM courses ORDER BY code ASC;", prepare=False)
            courses = [{"code": r[0], "title": r[1]} for r in cur.fetchall()]

    if not courses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No courses found in database to map documents against."
        )

    predictions = []
    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            predictions.append({
                "filename": file.filename,
                "error": "Not a PDF document",
                "valid": False
            })
            continue

        try:
            content = await file.read()
            reader = PdfReader(io.BytesIO(content))
            page_count = len(reader.pages)
            
            first_pages = ""
            for p in reader.pages[:2]:
                first_pages += sanitize_text(p.extract_text() or "") + "\n"

            res = classify_document_and_subject(first_pages, file.filename, courses)
            predictions.append({
                "filename": file.filename,
                "predicted_course_id": res["course_id"],
                "predicted_doc_type": res["doc_type"],
                "confidence": res.get("confidence", "heuristic"),
                "page_count": page_count,
                "valid": True
            })
        except Exception as exc:
            traceback.print_exc()
            predictions.append({
                "filename": file.filename,
                "error": str(exc),
                "valid": False
            })

    return {
        "available_courses": courses,
        "predictions": predictions
    }


@router.post("/upload-batch")
async def upload_batch_documents(
    files: List[UploadFile] = File(...),
    metadata: str = Form(...),  # JSON string: [{"filename": "...", "course_id": "...", "doc_type": "..."}, ...]
    current_user: dict = Depends(require_role("admin", "faculty"))
):
    """Processes, embeds, and ingests verified files into Supabase & pgvector."""
    try:
        meta_list = json.loads(metadata)
        meta_map = {m["filename"]: m for m in meta_list}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metadata JSON: {str(e)}"
        )

    user_id = current_user.get("id")
    results = []
    errors = []

    for file in files:
        clean_name = sanitize_text(file.filename)
        file_meta = meta_map.get(file.filename)
        if not file_meta:
            errors.append({"filename": clean_name, "error": "No matching metadata provided."})
            continue

        target_course = file_meta["course_id"].strip().upper()
        target_type = file_meta["doc_type"].strip()

        try:
            file_bytes = await file.read()
            if len(file_bytes) == 0:
                errors.append({"filename": clean_name, "error": "Empty file."})
                continue

            reader = PdfReader(io.BytesIO(file_bytes))
            
            # 1. Upload to Supabase Storage
            unique_filename = f"{uuid.uuid4()}_{clean_name}"
            storage_path = f"{target_course}/{target_type.replace(' ', '_')}/{unique_filename}"
            try:
                upload_pdf_to_storage(file_bytes, storage_path)
            except Exception as e:
                print(f"[STORAGE WARNING] Cloud storage skipped for {clean_name}: {e}")

            # 2. Database Insert & Fastembed vectorization
            doc_id = str(uuid.uuid4())
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO documents (id, course_id, doc_type, filename, storage_path, uploaded_by)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (doc_id, target_course, target_type, clean_name, storage_path, user_id),
                        prepare=False
                    )

                    # Extract & Sanitize Chunks
                    raw_chunks_meta = []
                    for page_idx, page in enumerate(reader.pages):
                        clean_page_text = sanitize_text(page.extract_text() or "")
                        if not clean_page_text.strip():
                            continue

                        chunks = chunk_text(clean_page_text, chunk_size=400, overlap=40)
                        for c in chunks:
                            clean_c = sanitize_text(c).strip()
                            if clean_c:
                                raw_chunks_meta.append((clean_c, page_idx + 1))

                    chunk_records = []
                    BATCH_SIZE = 32
                    for i in range(0, len(raw_chunks_meta), BATCH_SIZE):
                        batch = raw_chunks_meta[i:i + BATCH_SIZE]
                        texts = [item[0] for item in batch]
                        batch_vectors = get_embeddings_batch(texts)

                        for (c_text, page_num), vector in zip(batch, batch_vectors):
                            vec_str = f"[{','.join(map(str, vector))}]"
                            chunk_records.append((
                                str(uuid.uuid4()),
                                doc_id,
                                target_course,
                                target_type,
                                c_text,
                                vec_str,
                                page_num
                            ))

                    if chunk_records:
                        cur.executemany(
                            """
                            INSERT INTO document_chunks (
                                id, document_id, course_id, doc_type, content, embedding, page_number
                            )
                            VALUES (%s, %s, %s, %s, %s, %s::vector, %s);
                            """,
                            chunk_records,
                            returning=False
                        )
                conn.commit()

            results.append({
                "document_id": doc_id,
                "filename": clean_name,
                "course_id": target_course,
                "doc_type": target_type,
                "chunks_indexed": len(chunk_records)
            })

        except Exception as exc:
            traceback.print_exc()
            errors.append({"filename": clean_name, "error": str(exc)})

    return {
        "message": f"Successfully indexed {len(results)} file(s).",
        "processed": results,
        "failed": errors
    }


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
                (clean_code,),
                prepare=False
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