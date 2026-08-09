"""In-memory order book with price-time priority.

Deterministic: bids highest price first, asks lowest price first;
at equal price, earlier order_id wins (proxy for time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


@dataclass(order=True)
class BookLevelOrder:
    """Sort key depends on side; use factory helpers."""

    sort_price: Decimal
    sort_time: int
    order_id: int = field(compare=False)
    trader_id: int = field(compare=False)
    price: Decimal = field(compare=False)
    quantity: int = field(compare=False)


@dataclass
class OrderBook:
    stock_id: int
    bids: list[BookLevelOrder] = field(default_factory=list)
    asks: list[BookLevelOrder] = field(default_factory=list)

    def best_bid(self) -> BookLevelOrder | None:
        return self.bids[0] if self.bids else None

    def best_ask(self) -> BookLevelOrder | None:
        return self.asks[0] if self.asks else None

    def spread(self) -> Decimal | None:
        bid = self.best_bid()
        ask = self.best_ask()
        if bid is None or ask is None:
            return None
        return ask.price - bid.price

    def add_order(
        self,
        *,
        side: Literal["buy", "sell"],
        order_id: int,
        trader_id: int,
        price: Decimal,
        quantity: int,
    ) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if side == "buy":
            entry = BookLevelOrder(
                sort_price=-price,  # highest first
                sort_time=order_id,
                order_id=order_id,
                trader_id=trader_id,
                price=price,
                quantity=quantity,
            )
            self.bids.append(entry)
            self.bids.sort()
        else:
            entry = BookLevelOrder(
                sort_price=price,  # lowest first
                sort_time=order_id,
                order_id=order_id,
                trader_id=trader_id,
                price=price,
                quantity=quantity,
            )
            self.asks.append(entry)
            self.asks.sort()

    def remove_order(self, order_id: int) -> bool:
        for collection in (self.bids, self.asks):
            for i, entry in enumerate(collection):
                if entry.order_id == order_id:
                    del collection[i]
                    return True
        return False

    def update_quantity(self, order_id: int, quantity: int) -> bool:
        if quantity < 0:
            raise ValueError("quantity cannot be negative")
        for collection in (self.bids, self.asks):
            for i, entry in enumerate(collection):
                if entry.order_id == order_id:
                    if quantity == 0:
                        del collection[i]
                    else:
                        entry.quantity = quantity
                    return True
        return False

    def depth(self, levels: int = 10) -> dict:
        def aggregate(entries: list[BookLevelOrder]) -> list[dict]:
            buckets: dict[Decimal, int] = {}
            order: list[Decimal] = []
            for e in entries:
                if e.price not in buckets:
                    buckets[e.price] = 0
                    order.append(e.price)
                buckets[e.price] += e.quantity
            out = [{"price": str(p), "quantity": buckets[p]} for p in order[:levels]]
            return out

        return {
            "bids": aggregate(self.bids),
            "asks": aggregate(self.asks),
            "best_bid": str(self.best_bid().price) if self.best_bid() else None,
            "best_ask": str(self.best_ask().price) if self.best_ask() else None,
            "spread": str(self.spread()) if self.spread() is not None else None,
        }
