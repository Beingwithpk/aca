from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# --- Auth Models ---
class UserSignupRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(..., min_length=6)
    role: str = Field(default="student", pattern="^(student|faculty|admin)$")
    branch: Optional[str] = None
    scholar_no: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    branch: Optional[str] = None
    scholar_no: Optional[str] = None
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Course Models ---
class CourseCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=20)
    title: str = Field(..., min_length=2, max_length=255)
    semester: int = Field(default=1, ge=1, le=8)


class CourseOut(BaseModel):
    code: str
    title: str
    semester: int
    created_at: Optional[datetime] = None


# --- Document Models ---
class DocumentOut(BaseModel):
    id: str
    course_id: str
    doc_type: str
    filename: str
    storage_path: str
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None


# --- Chat Models ---
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatQueryRequest(BaseModel):
    course_id: str
    query: str
    history: Optional[List[ChatMessage]] = []


class ChatSourceOut(BaseModel):
    doc_type: Optional[str] = None
    page_number: Optional[int] = None
    content: str
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSourceOut]


# --- Attendance Models ---
class StudentAttendanceItem(BaseModel):
    student_id: str
    status: str = Field(..., pattern="^(present|absent|holiday|GT)$")


class BulkAttendanceRequest(BaseModel):
    course_id: str
    branch: str
    session_date: date
    records: List[StudentAttendanceItem]