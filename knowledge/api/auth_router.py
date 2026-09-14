from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from knowledge.api.deps import get_auth_service
from knowledge.auth.schemas import LoginRequest, LoginResponse, MeResponse
from knowledge.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录凭证缺失",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录凭证缺失",
        )
    return token


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    return service.login(body.username, body.password)


@router.get("/me", response_model=MeResponse)
def me(
    authorization: str | None = Header(default=None),
    service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    token = _extract_bearer(authorization)
    return service.me(token)
