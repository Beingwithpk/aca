import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.db import get_connection
from src.models import BulkAttendanceRequest
from src.security import get_current_user, require_role

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


@router.get("/roster")
def get_branch_roster(
    branch: str = Query(...),
    course_id: Optional[str] = Query(None),
    session_date: Optional[date] = Query(None),
    current_user: dict = Depends(require_role("faculty", "admin"))
):
    """Retrieve students enrolled in a branch with their attendance status for a given date."""
    clean_branch = branch.strip()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Fetch all students in this branch
            cur.execute(
                """
                SELECT id, full_name, email, scholar_no
                FROM users
                WHERE role = 'student' AND branch = %s
                ORDER BY scholar_no ASC, full_name ASC;
                """,
                (clean_branch,)
            )
            students = cur.fetchall()

            # Check if an attendance session already exists for this date and course
            existing_status_map = {}
            if course_id and session_date:
                cur.execute(
                    """
                    SELECT ar.student_id, ar.status
                    FROM attendance_records ar
                    JOIN attendance_sessions s ON ar.session_id = s.id
                    WHERE s.course_id = %s AND s.branch = %s AND s.session_date = %s;
                    """,
                    (course_id.strip().upper(), clean_branch, session_date)
                )
                for sid, stat in cur.fetchall():
                    existing_status_map[str(sid)] = stat

    roster = [
        {
            "student_id": str(s[0]),
            "full_name": s[1],
            "email": s[2],
            "scholar_no": s[3] or "N/A",
            "status": existing_status_map.get(str(s[0]), "present")
        }
        for s in students
    ]

    return {
        "branch": clean_branch,
        "total_students": len(roster),
        "roster": roster
    }


@router.post("/bulk", status_code=status.HTTP_200_OK)
def submit_bulk_attendance(
    payload: BulkAttendanceRequest,
    current_user: dict = Depends(require_role("faculty", "admin"))
):
    """Faculty/Admin: Record or update attendance for an entire class."""
    clean_course_id = payload.course_id.strip().upper()
    clean_branch = payload.branch.strip()
    marked_by = current_user.get("id")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Upsert attendance session
            cur.execute(
                """
                INSERT INTO attendance_sessions (course_id, branch, session_date, marked_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (course_id, branch, session_date)
                DO UPDATE SET marked_by = EXCLUDED.marked_by
                RETURNING id;
                """,
                (clean_course_id, clean_branch, payload.session_date, marked_by)
            )
            session_id = cur.fetchone()[0]

            # 2. Bulk upsert individual records
            records_data = [
                (session_id, item.student_id, item.status)
                for item in payload.records
            ]

            cur.executemany(
                """
                INSERT INTO attendance_records (session_id, student_id, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (session_id, student_id)
                DO UPDATE SET status = EXCLUDED.status;
                """,
                records_data
            )
        conn.commit()

    return {
        "message": "Attendance recorded successfully",
        "session_id": str(session_id),
        "records_updated": len(payload.records)
    }