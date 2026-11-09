import os
from dotenv import load_dotenv

load_dotenv(override=True)

# --- Database & Vector ---
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")

# --- JWT & Security ---
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "b91e92d7c041f238bcfb56c49a6231e847c1a2f64e10b129846d0a7931b209e5")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

# --- Supabase Storage & Client ---
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
# Aliases for backward/cross-module compatibility
SUPABASE_KEY: str = SUPABASE_SERVICE_ROLE_KEY
SUPABASE_STORAGE_BUCKET: str = os.getenv("SUPABASE_STORAGE_BUCKET", "academic-materials")
SUPABASE_BUCKET: str = SUPABASE_STORAGE_BUCKET

# --- LLM Client Configuration ---
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")

# Legacy/Groq Aliases
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", LLM_API_KEY)
GROQ_MODEL: str = os.getenv("GROQ_MODEL", LLM_MODEL)

# --- Embedding Configuration ---
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", 384))