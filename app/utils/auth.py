from ..config import Config
from flask import request, jsonify
from functools import wraps
import jwt
from jwt import PyJWKClient

PROJECT_ID = Config.SUPABASE_PROJECT_ID
JWT_SECRET = Config.SUPABASE_JWT_SECRET

JWKS_URL = f"https://{PROJECT_ID}.supabase.co/auth/v1/.well-known/jwks.json"

# Create JWKS client with cache enabled
jwks_client = PyJWKClient(JWKS_URL, cache_keys=True, max_cached_keys=16)

def verify_supabase_jwt(token: str):
    try:
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get('alg')

        if alg == 'ES256':
            print(f"[AUTH] Handling ES256 token (using JWKS)")
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
            except jwt.exceptions.PyJWKClientError as e:
                print(f"[AUTH] Key not found, refreshing JWKS cache...")
                jwks_client._cached_keys = None
                jwks_client._cached_at = 0
                signing_key = jwks_client.get_signing_key_from_jwt(token)

            public_key = signing_key.key
            decoded = jwt.decode(
                token,
                key=public_key,
                algorithms=["ES256"],
                options={"verify_aud": False},
                leeway=5
            )
            print(f"[AUTH] ES256 Token decoded successfully. User: {decoded.get('sub')}")
            return decoded
        else:
            raise ValueError(f"Unsupported algorithm: {alg}")

    except jwt.exceptions.DecodeError as e:
        print(f"[AUTH] JWT Decode Error: {e}")
        raise
    except Exception as e:
        print(f"[AUTH] Verification Error: {e}")
        raise


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0] != "Bearer":
            print(f"[AUTH] Invalid auth header format")
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = parts[1]
        try:
            user_claims = verify_supabase_jwt(token)
        except Exception as e:
            print(f"[AUTH] Auth failed: {e}")
            return jsonify({"error": "Unauthorized", "details": str(e)}), 401

        request.user = user_claims
        return f(*args, **kwargs)

    return wrapper