from flask_cors import CORS
from supabase import create_client
import os

cors = CORS()

def get_supabase_client():
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)