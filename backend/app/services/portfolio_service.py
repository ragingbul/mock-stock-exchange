"""Portfolio valuation from cash + holdings marked to last traded price."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Holding, Stock, Trader
from app.schemas import HoldingAdjust, HoldingRead, PortfolioRead
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
            # Return a detached snapshot for API convenience
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
    _ = holding.stock  # ensure relationship is available for API responses
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

    cash = Decimal(trader.cash)
    starting = Decimal(trader.starting_capital)
    realized = Decimal(trader.realized_pnl)
    unrealized_pnl = holdings_value - cost_basis
    portfolio_value = cash + holdings_value
    total_pnl = realized + unrealized_pnl
    return_pct = (
        ((portfolio_value - starting) / starting) * Decimal("100")
        if starting > 0
        else Decimal("0")
    )

    return PortfolioRead(
        trader_id=trader.id,
        name=trader.name,
        cash=cash,
        starting_capital=starting,
        holdings_value=holdings_value,
        portfolio_value=portfolio_value,
        realized_pnl=realized,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        return_pct=return_pct.quantize(Decimal("0.0001")),
        holdings=holdings_out,
    )
