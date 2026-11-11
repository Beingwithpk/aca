import contextlib
from psycopg_pool import ConnectionPool
from src.config import DATABASE_URL, EMBEDDING_DIM

# Initialize connection pool without auto-opening worker threads at import time
pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=10,
    open=True,
    kwargs={"prepare_threshold": False}
)
def get_connection():
    return pool.connection()

@contextlib.contextmanager
def get_connection():
    """Context manager for obtaining a database connection from the pool."""
    with pool.connection() as conn:
        yield conn

def close_pool():
    """Cleanly close connection pool workers on app shutdown."""
    try:
        pool.close()
    except Exception:
        pass

def init_tables():
    """Initializes all database tables with required relations and vector extensions."""
    schema_sql = f"""
    -- 1. Enable pgvector extension
    CREATE EXTENSION IF NOT EXISTS vector;

    -- 2. Users Table
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE NOT NULL,
        full_name VARCHAR(255) NOT NULL,
        hashed_password TEXT NOT NULL,
        role VARCHAR(50) NOT NULL DEFAULT 'student',
        branch VARCHAR(50),
        scholar_no VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- 3. Courses / Subjects Table
    CREATE TABLE IF NOT EXISTS courses (
        code VARCHAR(20) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        semester INT DEFAULT 1,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- 4. Documents Table
    CREATE TABLE IF NOT EXISTS documents (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        course_id VARCHAR(20) NOT NULL REFERENCES courses(code) ON DELETE CASCADE,
        doc_type VARCHAR(50) NOT NULL,
        filename VARCHAR(255) NOT NULL,
        storage_path TEXT NOT NULL,
        uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- 5. Document Chunks Table (pgvector)
    CREATE TABLE IF NOT EXISTS document_chunks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        course_id VARCHAR(20) NOT NULL REFERENCES courses(code) ON DELETE CASCADE,
        doc_type VARCHAR(50),
        content TEXT NOT NULL,
        embedding VECTOR({EMBEDDING_DIM}) NOT NULL,
        page_number INT,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    -- Vector similarity index (HNSW for fast cosine search)
    CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

    -- 6. Attendance Sessions Table
    CREATE TABLE IF NOT EXISTS attendance_sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        course_id VARCHAR(20) NOT NULL REFERENCES courses(code) ON DELETE CASCADE,
        branch VARCHAR(50) NOT NULL,
        session_date DATE NOT NULL,
        marked_by UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (course_id, branch, session_date)
    );

    -- 7. Attendance Records Table
    CREATE TABLE IF NOT EXISTS attendance_records (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id UUID NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
        student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        status VARCHAR(20) NOT NULL,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (session_id, student_id)
    );
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
    print("--- Database schema verified ---")