from dataclasses import dataclass

import jwt as pyjwt
from fastapi import Cookie, HTTPException, status

from core.auth.jwt import decode_token
from core import repository as repo


@dataclass
class CurrentUser:
    id: int
    email: str
    jti: str


def current_user(access_token: str | None = Cookie(default=None)) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증이 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if access_token is None:
        raise credentials_exception
    try:
        payload = decode_token(access_token)
    except pyjwt.InvalidTokenError:
        raise credentials_exception

    user_id = int(payload.get("sub", 0))
    email = payload.get("email", "")
    jti = payload.get("jti", "")

    if not user_id or not jti:
        raise credentials_exception

    if not repo.is_session_valid(jti):
        raise credentials_exception

    user = repo.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception

    return CurrentUser(id=user_id, email=email, jti=jti)
