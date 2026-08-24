"""Participant and admin authentication."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, enforce_join_rate_limit, enforce_rate_limit
from app.models.enums import TraderType
from app.schemas import TraderCreate
from app.services import trader_service

router = APIRouter(prefix="/auth", tags=["auth"])


class JoinRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=64)


class JoinResponse(BaseModel):
    trader_id: int
    display_name: str
    access_token: str
    token_type: str = "bearer"


class AdminLoginRequest(BaseModel):
    secret: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/join", response_model=JoinResponse)
def join_session(
    request: Request,
    payload: JoinRequest,
    db: Session = Depends(get_db),
) -> JoinResponse:
    enforce_join_rate_limit(request)
    suffix = secrets.token_hex(3)
    trader = trader_service.create_trader(
        db,
        TraderCreate(name=f"{payload.display_name}-{suffix}", trader_type=TraderType.HUMAN),
    )
    token = create_access_token(
        subject=str(trader.id),
        role="participant",
        trader_id=trader.id,
    )
    return JoinResponse(
        trader_id=trader.id,
        display_name=payload.display_name,
        access_token=token,
    )


@router.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(
    request: Request,
    payload: AdminLoginRequest,
) -> AdminLoginResponse:
    """Exchange ADMIN_SECRET for an admin bearer token."""
    from app.core.config import get_settings

    enforce_rate_limit(request)
    settings = get_settings()
    if payload.secret != settings.admin_secret:
        raise HTTPException(status_code=401, detail="invalid admin secret")
    token = create_access_token(subject="admin", role="admin")
    return AdminLoginResponse(access_token=token)


@router.post("/admin/token", response_model=AdminLoginResponse)
def admin_token_from_secret(
    request: Request,
    payload: AdminLoginRequest,
) -> AdminLoginResponse:
    """Alias for admin login."""
    return admin_login(request, payload)
