"""Mean reversion vs fair value."""

from __future__ import annotations

from decimal import Decimal

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy


class MeanReversionStrategy(TraderStrategy):
    name = "mean_reversion"

    def decide(self, view: MarketView, cash: Decimal, position: int) -> StrategyOrderIntent | None:
        band = float(self.config.get("band", 0.12))
        size = int(self.config.get("size", 40))
        if view.fair_value <= 0:
            return None
        gap = float((view.last_price - view.fair_value) / view.fair_value)
        if gap > band and position >= size:
            return StrategyOrderIntent(view.stock_id, "sell", "limit", size, view.last_price)
        if gap < -band and cash > view.last_price * size:
            return StrategyOrderIntent(view.stock_id, "buy", "limit", size, view.last_price)
        return None
