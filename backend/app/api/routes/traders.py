"""Trader and portfolio HTTP routes."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import HoldingAdjust, HoldingRead, PortfolioRead, TraderCreate, TraderRead, WalletRead
from app.services import portfolio_service, trader_service
from app.services.trader_service import TraderServiceError

router = APIRouter(prefix="/traders", tags=["traders"])


@router.post("", response_model=TraderRead, status_code=status.HTTP_201_CREATED)
def create_trader(payload: TraderCreate, db: Session = Depends(get_db)) -> TraderRead:
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
def get_portfolio(trader_id: int, db: Session = Depends(get_db)) -> PortfolioRead:
    try:
        return portfolio_service.get_portfolio(db, trader_id)
    except TraderServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{trader_id}/wallet", response_model=WalletRead)
def get_wallet(trader_id: int, db: Session = Depends(get_db)) -> WalletRead:
    try:
        return portfolio_service.get_wallet(db, trader_id)
    except TraderServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/{trader_id}/holdings", response_model=HoldingRead)
def set_holding(
    trader_id: int, payload: HoldingAdjust, db: Session = Depends(get_db)
) -> HoldingRead:
    """Phase 1 helper to seed holdings before settlement exists."""
    try:
        holding = portfolio_service.set_holding(db, trader_id, payload)
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
