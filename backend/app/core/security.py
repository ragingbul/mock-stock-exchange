"""JWT helpers and auth dependencies."""

from __future__ import annotations

import time
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Trader

_bearer = HTTPBearer(auto_error=False)

_rate_buckets: dict[str, list[float]] = {}


def create_access_token(*, subject: str, role: str = "participant", trader_id: int | None = None) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + settings.auth_token_expire_minutes * 60,
    }
    if trader_id is not None:
        payload["trader_id"] = trader_id
    return jwt.encode(payload, settings.auth_secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.auth_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request) -> None:
    settings = get_settings()
    key = _client_key(request)
    now = time.time()
    window = 60.0
    bucket = _rate_buckets.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    bucket.append(now)


def require_admin(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    enforce_rate_limit(request)
    settings = get_settings()
    if credentials is None:
        raise HTTPException(status_code=401, detail="admin authorization required")
    token = credentials.credentials
    if token == settings.admin_secret:
        return {"role": "admin", "sub": "admin-secret"}
    payload = decode_token(token)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin access required")
    return payload


def get_optional_trader(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Trader | None:
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    trader_id = payload.get("trader_id")
    if trader_id is None:
        return None
    return db.get(Trader, int(trader_id))


def require_trader(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Trader:
    enforce_rate_limit(request)
    if credentials is None:
        raise HTTPException(status_code=401, detail="authorization required")
    payload = decode_token(credentials.credentials)
    trader_id = payload.get("trader_id")
    if trader_id is None:
        raise HTTPException(status_code=401, detail="invalid participant token")
    trader = db.get(Trader, int(trader_id))
    if trader is None or not trader.is_active:
        raise HTTPException(status_code=401, detail="trader not found or inactive")
    return trader
