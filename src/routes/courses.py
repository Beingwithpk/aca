from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from src.db import get_connection
from src.models import CourseCreateRequest, CourseOut
from src.security import get_current_user, require_role

router = APIRouter(prefix="/api/courses", tags=["Courses"])


class CourseUpdateRequest(BaseModel):
    title: Optional[str] = None
    semester: Optional[int] = None


@router.get("", response_model=List[CourseOut])
def list_courses(current_user: dict = Depends(get_current_user)):
    """Fetch all available courses/subjects (accessible by students and admin)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT code, title, semester, created_at
                FROM courses
                ORDER BY code ASC;
                """,
                prepare=False
            )
            rows = cur.fetchall()

    return [
        {
            "code": r[0],
            "title": r[1],
            "semester": r[2],
            "created_at": r[3]
        }
        for r in rows
    ]


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreateRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Admin-only: Create a new course."""
    clean_code = payload.code.strip().upper()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code FROM courses WHERE code = %s;",
                (clean_code,),
                prepare=False
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Course '{clean_code}' already exists."
                )

            cur.execute(
                """
                INSERT INTO courses (code, title, semester)
                VALUES (%s, %s, %s)
                RETURNING code, title, semester, created_at;
                """,
                (clean_code, payload.title.strip(), payload.semester),
                prepare=False
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "code": row[0],
        "title": row[1],
        "semester": row[2],
        "created_at": row[3]
    }


@router.put("/{code}", response_model=CourseOut, status_code=status.HTTP_200_OK)
def update_course(
    code: str,
    payload: CourseUpdateRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Admin-only: Edit an existing course's title or semester."""
    clean_code = code.strip().upper()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT code, title, semester FROM courses WHERE code = %s;",
                (clean_code,),
                prepare=False
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Course '{clean_code}' not found."
                )

            new_title = payload.title.strip() if payload.title is not None else existing[1]
            new_semester = payload.semester if payload.semester is not None else existing[2]

            cur.execute(
                """
                UPDATE courses
                SET title = %s, semester = %s
                WHERE code = %s
                RETURNING code, title, semester, created_at;
                """,
                (new_title, new_semester, clean_code),
                prepare=False
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "code": row[0],
        "title": row[1],
        "semester": row[2],
        "created_at": row[3]
    }


@router.delete("/{code}", status_code=status.HTTP_200_OK)
def delete_course(
    code: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Admin-only: Delete a course and all associated materials."""
    clean_code = code.strip().upper()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM courses WHERE code = %s RETURNING code;",
                (clean_code,),
                prepare=False
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Course '{clean_code}' not found."
                )
        conn.commit()

    return {"message": f"Course '{clean_code}' and all related materials deleted."}