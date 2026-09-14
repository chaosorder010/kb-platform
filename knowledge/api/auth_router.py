from __future__ import annotations

from fastapi import APIRouter, Depends

from knowledge.api.deps import get_auth_service, get_current_user
from knowledge.auth.schemas import LoginRequest, LoginResponse, MeResponse
from knowledge.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    return service.login(body.username, body.password)


@router.get("/me", response_model=MeResponse)
def me(user: MeResponse = Depends(get_current_user)) -> MeResponse:
    return user
