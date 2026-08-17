"""Rebuild in-memory order books from persisted open orders."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exchange.book_registry import books
from app.exchange.matching_engine import MatchingEngine
from app.models import Order, Stock
from app.models.enums import StockStatus
from app.models.order_enums import OrderSide, OrderStatus, OrderType

_engine = MatchingEngine()


def clear_books() -> None:
    books.clear()


def rebuild_books_from_db(db: Session) -> int:
    """Load valid open limit orders into in-memory books. Returns count restored."""
    books.clear()
    stmt = (
        select(Order)
        .join(Stock, Stock.id == Order.stock_id)
        .where(
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            Order.order_type == OrderType.LIMIT,
            Stock.status == StockStatus.ACTIVE.value,
            Stock.is_open.is_(True),
        )
    )
    orders = list(db.scalars(stmt).all())
    for order in orders:
        if order.price is None or order.remaining_quantity <= 0:
            continue
        book = books.get(order.stock_id)
        _engine.match(
            book,
            order_id=order.id,
            trader_id=order.trader_id,
            side=order.side,
            order_type=OrderType.LIMIT,
            quantity=order.remaining_quantity,
            limit_price=Decimal(order.price),
        )
    return len(orders)


def cancel_stale_open_orders(db: Session) -> int:
    """Cancel open orders on dissolved/closed stocks."""
    stmt = select(Order).where(
        Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
    )
    cancelled = 0
    for order in db.scalars(stmt).all():
        stock = db.get(Stock, order.stock_id)
        if stock is None or stock.status != StockStatus.ACTIVE.value or not stock.is_open:
            books.get(order.stock_id).remove_order(order.id)
            order.status = OrderStatus.CANCELLED
            order.remaining_quantity = 0
            cancelled += 1
    if cancelled:
        db.commit()
    return cancelled
