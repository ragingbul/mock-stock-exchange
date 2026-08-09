"""FOMO trader — exaggerates upside momentum and bullish news."""

from __future__ import annotations

from decimal import Decimal
import random

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy


class FomoStrategy(TraderStrategy):
    name = "fomo"

    def decide(self, view: MarketView, cash: Decimal, position: int) -> StrategyOrderIntent | None:
        size = int(self.config.get("size", 40))
        rng = random.Random(hash((view.ticker, "fomo", round(view.signal, 4))) & 0xFFFFFFFF)
        bullish = view.recent_return > 0.01 or view.news_impact > 0.2 or view.signal > 0.15
        if bullish and cash > view.last_price * size and rng.random() < 0.8:
            return StrategyOrderIntent(view.stock_id, "buy", "market", size)
        return None
