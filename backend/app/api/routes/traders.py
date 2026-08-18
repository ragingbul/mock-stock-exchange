"""Trader and portfolio HTTP routes."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import require_admin, require_trader
from app.models import Trader
from app.schemas import HoldingAdjust, HoldingRead, PortfolioRead, TraderCreate, TraderRead, WalletRead
from app.services import portfolio_service, trader_service
from app.services.trader_service import TraderServiceError

router = APIRouter(prefix="/traders", tags=["traders"])
_bearer = HTTPBearer(auto_error=False)


def _require_trader_create_admin(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict | None:
    if not get_settings().is_production:
        return None
    return require_admin(request, credentials)


def _optional_trader_for_holdings(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Trader | None:
    if not get_settings().is_production:
        return None
    return require_trader(request, db, credentials)


@router.post("", response_model=TraderRead, status_code=status.HTTP_201_CREATED)
def create_trader(
    payload: TraderCreate,
    db: Session = Depends(get_db),
    _auth: dict | None = Depends(_require_trader_create_admin),
) -> TraderRead:
    try:
        trader = trader_service.create_trader(db, payload)
    except TraderServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TraderRead.model_validate(trader)


@router.get("", response_model=list[TraderRead])
def list_traders(db: Session = Depends(get_db)) -> list[TraderRead]:
    return [TraderRead.model_validate(t) for t in trader_service.list_traders(db)]


@router.get("/{trader_id}", response_model=TraderRead)
def get_trader(trader_id: int, db: Session = Depends(get_db)) -> TraderRead:
    trader = trader_service.get_trader(db, trader_id)
    if trader is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trader not found")
    return TraderRead.model_validate(trader)


@router.get("/{trader_id}/portfolio", response_model=PortfolioRead)
def get_portfolio(
    trader_id: int,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> PortfolioRead:
    if trader_id != trader.id:
        raise HTTPException(status_code=403, detail="trader_id does not match authenticated session")
    try:
        return portfolio_service.get_portfolio(db, trader.id)
    except TraderServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{trader_id}/wallet", response_model=WalletRead)
def get_wallet(
    trader_id: int,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> WalletRead:
    if trader_id != trader.id:
        raise HTTPException(status_code=403, detail="trader_id does not match authenticated session")
    try:
        return portfolio_service.get_wallet(db, trader.id)
    except TraderServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{trader_id}/holdings", response_model=HoldingRead)
def set_holding(
    trader_id: int,
    payload: HoldingAdjust,
    db: Session = Depends(get_db),
    auth_trader: Trader | None = Depends(_optional_trader_for_holdings),
) -> HoldingRead:
    """Phase 1 helper to seed holdings before settlement exists."""
    if get_settings().is_production:
        if auth_trader is None or trader_id != auth_trader.id:
            raise HTTPException(status_code=403, detail="trader_id does not match authenticated session")
        effective_id = auth_trader.id
    else:
        effective_id = trader_id
    try:
        holding = portfolio_service.set_holding(db, effective_id, payload)
    except TraderServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    stock = holding.stock if getattr(holding, "stock", None) is not None else None
    market_price = stock.last_traded_price if stock is not None else None
    market_value = (
        market_price * holding.quantity if market_price is not None else Decimal("0")
    )
    unrealized = (
        market_value - (holding.avg_cost * holding.quantity)
        if market_price is not None
        else Decimal("0")
    )
    return HoldingRead(
        id=holding.id if holding.id is not None else 0,
        stock_id=holding.stock_id,
        ticker=stock.ticker if stock else None,
        quantity=holding.quantity,
        avg_cost=holding.avg_cost,
        market_price=market_price,
        market_value=market_value,
        unrealized_pnl=unrealized,
    )
