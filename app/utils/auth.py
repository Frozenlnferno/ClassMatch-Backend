import jwt
import requests
import os
from flask import request, jsonify
from functools import wraps

PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID")
JWKS_URL = f"https://{PROJECT_ID}.supabase.co/auth/v1/jwks"
jwks = requests.get(JWKS_URL).json()

def verify_supabase_jwt(token):
    header = jwt.get_unverified_header(token)
    for key in jwks["keys"]:
        if key["kid"] == header["kid"]:
            return jwt.decode(
                token,
                jwt.algorithms.RSAAlgorithm.from_jwk(key),
                algorithms=["RS256"],
                audience="authenticated"
            )
    raise Exception("Invalid Supabase JWT")

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "").split(" ")
        if len(auth) != 2 or auth[0] != "Bearer":
            return jsonify({"error": "Missing access token"}), 401
        
        token = auth[1]
        try:
            user = verify_supabase_jwt(token)
            request.user = user
        except Exception as e:
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)
    return wrapper
