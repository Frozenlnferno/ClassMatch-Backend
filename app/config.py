import os

class Config:
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    DB_SSLMODE = os.getenv("DB_SSLMODE", "require")  # prod default