"""In-process registry of order books keyed by stock_id."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exchange.order_book import OrderBook
from app.models import Order
from app.models.order_enums import OrderSide, OrderStatus, OrderType


class OrderBookRegistry:
    def __init__(self) -> None:
        self._books: dict[int, OrderBook] = {}

    def get(self, stock_id: int) -> OrderBook:
        if stock_id not in self._books:
            self._books[stock_id] = OrderBook(stock_id=stock_id)
        return self._books[stock_id]

    def clear(self) -> None:
        self._books.clear()

    def rebuild_from_db(self, db: Session) -> int:
        """Restore in-memory books from open limit orders after a process restart."""
        self.clear()
        stmt = (
            select(Order)
            .where(
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                Order.order_type == OrderType.LIMIT,
                Order.price.isnot(None),
            )
            .order_by(Order.id)
        )
        count = 0
        for order in db.scalars(stmt):
            assert order.price is not None
            book = self.get(order.stock_id)
            book.add_order(
                side="buy" if order.side == OrderSide.BUY else "sell",
                order_id=order.id,
                trader_id=order.trader_id,
                price=Decimal(order.price),
                quantity=order.remaining_quantity,
            )
            count += 1
        return count


# Process-wide registry (rebuilt from DB open orders on startup if needed)
books = OrderBookRegistry()
