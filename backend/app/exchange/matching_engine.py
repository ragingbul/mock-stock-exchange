"""Matching engine — pure order-book matching, no AI/news/UI deps."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.exchange.order_book import OrderBook
from app.models.order_enums import OrderSide, OrderType


@dataclass
class MatchFill:
    buy_order_id: int
    sell_order_id: int
    buyer_id: int
    seller_id: int
    price: Decimal
    quantity: int


@dataclass
class MatchResult:
    fills: list[MatchFill]
    remaining_quantity: int
    resting: bool  # True if leftover limit qty was booked


class MatchingEngine:
    """Match an incoming order against the opposite side of the book."""

    def match(
        self,
        book: OrderBook,
        *,
        order_id: int,
        trader_id: int,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        limit_price: Decimal | None,
    ) -> MatchResult:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if order_type == OrderType.LIMIT and limit_price is None:
            raise ValueError("limit orders require a price")

        fills: list[MatchFill] = []
        remaining = quantity

        while remaining > 0:
            opposite = book.best_ask() if side == OrderSide.BUY else book.best_bid()
            if opposite is None:
                break
            if opposite.trader_id == trader_id:
                # No self-trade: skip this resting order by treating book as blocked
                # Simple rule: stop matching to avoid complex skip logic for Phase 4
                break

            if order_type == OrderType.LIMIT:
                assert limit_price is not None
                if side == OrderSide.BUY and limit_price < opposite.price:
                    break
                if side == OrderSide.SELL and limit_price > opposite.price:
                    break

            trade_qty = min(remaining, opposite.quantity)
            trade_price = opposite.price  # resting order sets price (price-time)

            if side == OrderSide.BUY:
                fills.append(
                    MatchFill(
                        buy_order_id=order_id,
                        sell_order_id=opposite.order_id,
                        buyer_id=trader_id,
                        seller_id=opposite.trader_id,
                        price=trade_price,
                        quantity=trade_qty,
                    )
                )
            else:
                fills.append(
                    MatchFill(
                        buy_order_id=opposite.order_id,
                        sell_order_id=order_id,
                        buyer_id=opposite.trader_id,
                        seller_id=trader_id,
                        price=trade_price,
                        quantity=trade_qty,
                    )
                )

            remaining -= trade_qty
            new_opp_qty = opposite.quantity - trade_qty
            book.update_quantity(opposite.order_id, new_opp_qty)

        resting = False
        if remaining > 0 and order_type == OrderType.LIMIT:
            assert limit_price is not None
            book.add_order(
                side="buy" if side == OrderSide.BUY else "sell",
                order_id=order_id,
                trader_id=trader_id,
                price=limit_price,
                quantity=remaining,
            )
            resting = True

        return MatchResult(fills=fills, remaining_quantity=remaining, resting=resting)
