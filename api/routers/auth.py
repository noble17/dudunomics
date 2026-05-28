import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr

from core.auth.deps import CurrentUser, current_user
from core.auth.jwt import create_token, decode_token
from core.auth.passwords import hash_password, verify_password
from core import repository as repo

router = APIRouter(prefix="/api/auth", tags=["auth"])

_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "10080"))
_ALLOW_SIGNUP = os.getenv("ALLOW_SIGNUP", "true").lower() == "true"
_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


class SignupIn(BaseModel):
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=_TTL_MIN * 60,
        path="/",
    )


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, response: Response):
    if not _ALLOW_SIGNUP:
        raise HTTPException(status_code=403, detail="회원가입이 비활성화되어 있습니다.")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="비밀번호는 6자 이상이어야 합니다.")
    if repo.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다.")

    pw_hash = hash_password(body.password)
    user_id = repo.create_user(body.email, pw_hash)

    token, jti = create_token(user_id, body.email)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_TTL_MIN)
    repo.create_session(jti, user_id, expires_at)
    _set_auth_cookie(response, token)
    return UserOut(id=user_id, email=body.email)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response):
    user = repo.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    token, jti = create_token(user["id"], user["email"])
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_TTL_MIN)
    repo.create_session(jti, user["id"], expires_at)
    _set_auth_cookie(response, token)
    return UserOut(id=user["id"], email=user["email"])


@router.post("/logout")
def logout(response: Response, user: CurrentUser = Depends(current_user)):
    repo.revoke_session(user.jti)
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(current_user)):
    return UserOut(id=user.id, email=user.email)
