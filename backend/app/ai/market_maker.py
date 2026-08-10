"""Market maker — two-sided quotes around reference, inventory-aware."""

from __future__ import annotations

from decimal import Decimal

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy


class MarketMakerStrategy(TraderStrategy):
    name = "market_maker"

    def decide(self, view: MarketView, cash: Decimal, position: int) -> StrategyOrderIntent | None:
        spread_bps = float(self.config.get("spread_bps", 120))
        size = int(self.config.get("quote_size", 35))
        max_pos = int(self.config.get("max_position", 2000))
        mid = view.last_price
        half = mid * Decimal(str(spread_bps / 10000))
        # Inventory skew: long → lean sell
        skew = Decimal("0")
        if position > max_pos * 0.5:
            skew = half * Decimal("0.5")
        elif position < -max_pos * 0.5:
            skew = -half * Decimal("0.5")

        # Alternate: if flat-ish, place buy below; if long, place sell
        if position >= max_pos:
            return StrategyOrderIntent(
                stock_id=view.stock_id,
                side="sell",
                order_type="limit",
                quantity=size,
                price=(mid + half + skew),
            )
        if cash < mid * size:
            return None
        if position <= 0:
            return StrategyOrderIntent(
                stock_id=view.stock_id,
                side="buy",
                order_type="limit",
                quantity=size,
                price=(mid - half + skew),
            )
        return StrategyOrderIntent(
            stock_id=view.stock_id,
            side="sell",
            order_type="limit",
            quantity=size,
            price=(mid + half + skew),
        )
