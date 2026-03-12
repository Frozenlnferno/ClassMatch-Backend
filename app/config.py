import os

class Config:
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    DATABASE_URL = os.getenv("DATABASE_URL")
    DB_SSLMODE = os.getenv("DB_SSLMODE", "require")  # prod default
    JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"