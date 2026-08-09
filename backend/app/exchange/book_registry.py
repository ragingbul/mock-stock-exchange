"""In-process registry of order books keyed by stock_id."""

from __future__ import annotations

from app.exchange.order_book import OrderBook


class OrderBookRegistry:
    def __init__(self) -> None:
        self._books: dict[int, OrderBook] = {}

    def get(self, stock_id: int) -> OrderBook:
        if stock_id not in self._books:
            self._books[stock_id] = OrderBook(stock_id=stock_id)
        return self._books[stock_id]

    def clear(self) -> None:
        self._books.clear()


# Process-wide registry (rebuilt from DB open orders on startup if needed)
books = OrderBookRegistry()
