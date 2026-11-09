from datetime import datetime, timedelta, timezone
from typing import Optional, List
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from src.db import get_connection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# --- Password Cryptography ---
def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    pwd_bytes = plain_password.encode("utf-8")
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        plain_bytes = plain_password.encode("utf-8")
        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode("utf-8")
        else:
            hashed_bytes = hashed_password
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception:
        return False


# --- JWT Token Generation ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


# --- User Dependency Injection ---
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, full_name, role, branch, scholar_no, created_at
                FROM users
                WHERE id::text = %s;
                """,
                (user_id,)
            )
            row = cur.fetchone()

    if row is None:
        raise credentials_exception

    return {
        "id": str(row[0]),
        "email": row[1],
        "full_name": row[2],
        "role": row[3],
        "branch": row[4],
        "scholar_no": row[5],
        "created_at": row[6]
    }


# --- Role-Based Access Control Factory ---
def require_role(*allowed_roles: str):
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of following roles: {list(allowed_roles)}"
            )
        return current_user
    return role_checker