"""Portfolio valuation from cash + holdings marked to last traded price."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Holding, Stock, Trader
from app.schemas import HoldingAdjust, HoldingRead, PortfolioRead, WalletRead
from app.services.trader_service import TraderServiceError


def set_holding(db: Session, trader_id: int, payload: HoldingAdjust) -> Holding:
    """Set absolute holding quantity/cost (Phase 1 seeding; settlement comes later)."""
    trader = db.get(Trader, trader_id)
    if trader is None:
        raise TraderServiceError(f"trader not found: {trader_id}")

    stock = db.get(Stock, payload.stock_id)
    if stock is None:
        raise TraderServiceError(f"stock not found: {payload.stock_id}")

    holding = db.scalar(
        select(Holding).where(
            Holding.trader_id == trader_id,
            Holding.stock_id == payload.stock_id,
        )
    )
    if payload.quantity == 0:
        if holding is not None:
            db.delete(holding)
            db.commit()
            holding = Holding(
                trader_id=trader_id,
                stock_id=payload.stock_id,
                quantity=0,
                avg_cost=Decimal("0"),
            )
            return holding
        holding = Holding(
            trader_id=trader_id,
            stock_id=payload.stock_id,
            quantity=0,
            avg_cost=Decimal("0"),
        )
        return holding

    if holding is None:
        holding = Holding(
            trader_id=trader_id,
            stock_id=payload.stock_id,
            quantity=payload.quantity,
            avg_cost=payload.avg_cost,
        )
        db.add(holding)
    else:
        holding.quantity = payload.quantity
        holding.avg_cost = payload.avg_cost

    db.commit()
    db.refresh(holding)
    _ = holding.stock
    return holding


def get_portfolio(db: Session, trader_id: int) -> PortfolioRead:
    trader = db.scalar(
        select(Trader)
        .where(Trader.id == trader_id)
        .options(joinedload(Trader.holdings).joinedload(Holding.stock))
    )
    if trader is None:
        raise TraderServiceError(f"trader not found: {trader_id}")

    holdings_out: list[HoldingRead] = []
    holdings_value = Decimal("0")
    cost_basis = Decimal("0")

    for holding in trader.holdings:
        if holding.quantity <= 0:
            continue
        price = holding.stock.last_traded_price
        market_value = price * holding.quantity
        position_cost = holding.avg_cost * holding.quantity
        unrealized = market_value - position_cost
        holdings_value += market_value
        cost_basis += position_cost
        holdings_out.append(
            HoldingRead(
                id=holding.id,
                stock_id=holding.stock_id,
                ticker=holding.stock.ticker,
                quantity=holding.quantity,
                avg_cost=holding.avg_cost,
                market_price=price,
                market_value=market_value,
                unrealized_pnl=unrealized,
            )
        )

    available = Decimal(trader.cash)
    blocked = Decimal(getattr(trader, "cash_blocked_ipo", 0) or 0)
    starting = Decimal(trader.starting_capital)
    realized = Decimal(trader.realized_pnl)
    unrealized_pnl = holdings_value - cost_basis
    # Portfolio includes available cash + IPO-blocked cash + marked holdings
    portfolio_value = available + blocked + holdings_value
    total_pnl = realized + unrealized_pnl
    return_pct = (
        ((portfolio_value - starting) / starting) * Decimal("100")
        if starting > 0
        else Decimal("0")
    )

    return PortfolioRead(
        trader_id=trader.id,
        name=trader.name,
        cash=available,
        cash_blocked_ipo=blocked,
        available_cash=available,
        invested=holdings_value,
        starting_capital=starting,
        holdings_value=holdings_value,
        portfolio_value=portfolio_value,
        realized_pnl=realized,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        return_pct=return_pct.quantize(Decimal("0.0001")),
        holdings=holdings_out,
    )


def get_wallet(db: Session, trader_id: int) -> WalletRead:
    p = get_portfolio(db, trader_id)
    return WalletRead(
        trader_id=p.trader_id,
        available_cash=p.available_cash,
        cash_blocked_ipo=p.cash_blocked_ipo,
        invested=p.invested,
        portfolio_value=p.portfolio_value,
        total_pnl=p.total_pnl,
        return_pct=p.return_pct,
        starting_capital=p.starting_capital,
    )
