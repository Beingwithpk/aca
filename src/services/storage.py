from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_STORAGE_BUCKET

_supabase_client: Client | None = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured in .env")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client

def upload_pdf_to_storage(file_bytes: bytes, destination_path: str) -> str:
    """Uploads PDF bytes to the configured Supabase Storage bucket."""
    supabase = get_supabase_client()
    bucket = supabase.storage.from_(SUPABASE_STORAGE_BUCKET)
    bucket.upload(
        path=destination_path,
        file=file_bytes,
        file_options={"content-type": "application/pdf"}
    )
    return destination_path

def get_signed_pdf_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generates a temporary signed URL for viewing/downloading a PDF."""
    supabase = get_supabase_client()
    bucket = supabase.storage.from_(SUPABASE_STORAGE_BUCKET)
    res = bucket.create_signed_url(storage_path, expires_in)
    
    signed_url = res.get("signedURL") or res.get("signedUrl")
    if not signed_url:
        raise RuntimeError(f"Failed to generate signed URL: {res}")
    return signed_url

def delete_pdf_from_storage(destination_path: str):
    """Deletes a file from Supabase Storage."""
    supabase = get_supabase_client()
    bucket = supabase.storage.from_(SUPABASE_STORAGE_BUCKET)
    bucket.remove([destination_path])