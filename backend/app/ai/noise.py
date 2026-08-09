"""Noise trader — bounded random orders."""

from __future__ import annotations

from decimal import Decimal
import random

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy
from app.core.config import get_settings


class NoiseStrategy(TraderStrategy):
    name = "noise"

    def decide(self, view: MarketView, cash: Decimal, position: int) -> StrategyOrderIntent | None:
        size = int(self.config.get("size", 10))
        settings = get_settings()
        rng = random.Random(settings.random_seed + hash(view.ticker) + int(position))
        if rng.random() > 0.3:
            return None
        if rng.random() < 0.5 and cash > view.last_price * size:
            return StrategyOrderIntent(view.stock_id, "buy", "limit", size, view.last_price)
        if position >= size:
            return StrategyOrderIntent(view.stock_id, "sell", "limit", size, view.last_price)
        return None
