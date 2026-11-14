from fastapi import APIRouter, HTTPException, Depends, status
from src.db import get_connection
from src.models import UserSignupRequest, UserLoginRequest, UserOut, TokenResponse
from src.security import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/signup", response_model=UserOut)
def signup(payload: UserSignupRequest):
    email_clean = payload.email.strip().lower()

    # Check if user already exists
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE LOWER(email) = %s;", (email_clean,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A user with this email already exists."
                )

            # Enforce student-only registration (ignores any admin/faculty role sent in payload)
            enforced_role = "student"
            hashed_pw = hash_password(payload.password)

            cur.execute(
                """
                INSERT INTO users (email, full_name, hashed_password, role, branch, scholar_no)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, email, full_name, role, branch, scholar_no, created_at;
                """,
                (
                    email_clean,
                    payload.full_name.strip(),
                    hashed_pw,
                    enforced_role,
                    payload.branch.strip() if payload.branch else None,
                    payload.scholar_no.strip() if payload.scholar_no else None
                )
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "id": str(row[0]),
        "email": row[1],
        "full_name": row[2],
        "role": row[3],
        "branch": row[4],
        "scholar_no": row[5],
        "created_at": row[6]
    }


@router.post("/login", response_model=TokenResponse)
def login(creds: UserLoginRequest):
    email_clean = creds.email.strip().lower()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, full_name, hashed_password, role, branch, scholar_no, created_at
                FROM users
                WHERE LOWER(email) = %s;
                """,
                (email_clean,)
            )
            row = cur.fetchone()

    if not row or not verify_password(creds.password, row[3]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    user_out = {
        "id": str(row[0]),
        "email": row[1],
        "full_name": row[2],
        "role": row[4],
        "branch": row[5],
        "scholar_no": row[6],
        "created_at": row[7]
    }

    token = create_access_token(
        data={"sub": user_out["id"], "role": user_out["role"]}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_out
    }


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: dict = Depends(get_current_user)):
    return current_user