"""Panic trader — exaggerates downside and bearish news."""

from __future__ import annotations

import random

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy


class PanicStrategy(TraderStrategy):
    name = "panic"

    def decide(self, view: MarketView, cash, position: int) -> StrategyOrderIntent | None:
        size = int(self.config.get("size", 40))
        rng = random.Random(hash((view.ticker, "panic", round(view.signal, 4))) & 0xFFFFFFFF)
        bearish = view.recent_return < -0.01 or view.news_impact < -0.2 or view.signal < -0.15
        if bearish and position >= size and rng.random() < 0.85:
            return StrategyOrderIntent(view.stock_id, "sell", "market", min(size, position))
        return None
