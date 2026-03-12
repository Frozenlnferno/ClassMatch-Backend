from flask import request, jsonify, g
from functools import wraps
import jwt
from jwt import InvalidTokenError
from jwt import PyJWKClient
from app.config import Config

jwks_client = PyJWKClient(Config.JWKS_URL)

def verify_supabase_jwt(token: str):
    signing_key = jwks_client.get_signing_key_from_jwt(token).key

    decoded = jwt.decode(
        token,
        signing_key,
        algorithms=["ES256"],
        audience="authenticated",
        options={"require": ["exp", "iat", "sub"]},
        leeway=5,
    )
    return decoded

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ", 1)[1]
        try:
            claims = verify_supabase_jwt(token)
        except InvalidTokenError:
            return jsonify({"error": "Unauthorized"}), 401

        g.user = claims
        return f(*args, **kwargs)

    return wrapper