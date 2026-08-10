"""Momentum trader."""

from __future__ import annotations

from decimal import Decimal
import random

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy


class MomentumStrategy(TraderStrategy):
    name = "momentum"

    def decide(self, view: MarketView, cash: Decimal, position: int) -> StrategyOrderIntent | None:
        thr = float(self.config.get("threshold", 0.001))
        size = int(self.config.get("size", 80))
        aggressiveness = float(self.config.get("aggressiveness", 0.95))
        rng = random.Random(hash((view.ticker, round(view.recent_return, 5))) & 0xFFFFFFFF)
        news_boost = 1.0 + min(abs(view.news_impact), 2.0) * 0.35
        size = int(size * news_boost)
        if abs(view.recent_return) < thr:
            return None
        if rng.random() > aggressiveness:
            return None
        if view.recent_return > 0 and cash > view.last_price * size:
            return StrategyOrderIntent(view.stock_id, "buy", "market", size)
        if view.recent_return < 0 and position >= size:
            return StrategyOrderIntent(view.stock_id, "sell", "market", size)
        return None
