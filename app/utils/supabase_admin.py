from typing import Union

from supabase import create_client

from app.config import Config

_supabase_admin_client = None
DEFAULT_STORAGE_BUCKET = "images"


def get_supabase_admin_client():
    global _supabase_admin_client

    if _supabase_admin_client is None:
        if not Config.SUPABASE_URL or not Config.SUPABASE_SECRET_KEY:
            raise RuntimeError("Supabase admin client is not configured")

        _supabase_admin_client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_SECRET_KEY,
        )

    return _supabase_admin_client


def upload_public_file(
    object_path: str,
    file_data: Union[bytes, bytearray],
    content_type: str,
    bucket_name: str = DEFAULT_STORAGE_BUCKET,
) -> str:
    if not object_path:
        raise ValueError("object_path is required")
    if not file_data:
        raise ValueError("file_data is required")
    if not content_type:
        raise ValueError("content_type is required")

    bucket = get_supabase_admin_client().storage.from_(bucket_name)
    bucket.upload(
        object_path,
        bytes(file_data),
        file_options={
            "content-type": content_type,
            "cache-control": "3600",
            "upsert": "false",
        },
    )
    public_url = bucket.get_public_url(object_path)
    if not public_url:
        raise RuntimeError("Failed to generate public URL for uploaded file")
    return public_url
