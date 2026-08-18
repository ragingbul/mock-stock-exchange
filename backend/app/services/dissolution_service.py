"""Automated company dissolution and holding liquidation."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exchange.book_registry import books
from app.models import Holding, Stock, Trader
from app.models.enums import StockStatus
from app.models.order_enums import OrderStatus
from app.models import Order


class DissolutionError(Exception):
    pass


def dissolve_company(
    db: Session,
    *,
    ticker: str,
    liquidation_price: Decimal | float,
    headline: str | None = None,
) -> dict:
    stock = db.scalar(select(Stock).where(Stock.ticker == ticker.upper()))
    if stock is None:
        raise DissolutionError(f"stock not found: {ticker}")
    if stock.status == StockStatus.DISSOLVED.value:
        return {"ticker": stock.ticker, "already_dissolved": True}

    liq = Decimal(str(liquidation_price))
    stock.status = StockStatus.DISSOLVED.value
    stock.is_open = False
    stock.is_halted = True
    stock.liquidation_price = liq

    # Cancel open orders
    for order in db.scalars(
        select(Order).where(
            Order.stock_id == stock.id,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
        )
    ).all():
        books.get(stock.id).remove_order(order.id)
        order.status = OrderStatus.CANCELLED
        order.remaining_quantity = 0

    liquidated = 0
    total_paid = Decimal("0")
    for holding in db.scalars(select(Holding).where(Holding.stock_id == stock.id)).all():
        if holding.quantity <= 0:
            continue
        trader = db.get(Trader, holding.trader_id)
        if trader is None:
            continue
        payout = liq * holding.quantity
        trader.cash += payout
        cost = holding.avg_cost * holding.quantity
        trader.realized_pnl += payout - cost
        total_paid += payout
        liquidated += holding.quantity
        holding.quantity = 0
        holding.avg_cost = Decimal("0")

    db.commit()
    return {
        "ticker": stock.ticker,
        "liquidation_price": str(liq),
        "headline": headline,
        "holdings_liquidated": liquidated,
        "total_payout": str(total_paid),
    }
