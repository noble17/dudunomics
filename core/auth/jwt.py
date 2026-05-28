import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

_SECRET = os.getenv("JWT_SECRET", "change-me-please-use-a-real-secret")
_ALG = os.getenv("JWT_ALG", "HS256")
_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "10080"))  # 7 days


def create_token(user_id: int, email: str) -> tuple[str, str]:
    """Returns (token, jti)."""
    jti = str(uuid.uuid4())
    exp = datetime.now(timezone.utc) + timedelta(minutes=_TTL_MIN)
    payload = {"sub": str(user_id), "email": email, "jti": jti, "exp": exp}
    token = jwt.encode(payload, _SECRET, algorithm=_ALG)
    return token, jti


def decode_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, _SECRET, algorithms=[_ALG])
