"""Panic trader — exaggerates downside and bearish news."""

from __future__ import annotations

import random

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy


class PanicStrategy(TraderStrategy):
    name = "panic"

    def decide(self, view: MarketView, cash, position: int) -> StrategyOrderIntent | None:
        size = int(self.config.get("size", 100))
        rng = random.Random(hash((view.ticker, "panic", round(view.signal, 4))) & 0xFFFFFFFF)
        news_thr = float(self.config.get("news_threshold", -0.08))
        ret_thr = float(self.config.get("return_threshold", -0.003))
        sig_thr = float(self.config.get("signal_threshold", -0.05))
        fire_rate = float(self.config.get("fire_rate", 0.92))
        bearish = (
            view.recent_return < ret_thr
            or view.news_impact < news_thr
            or view.signal < sig_thr
        )
        if bearish and position >= size and rng.random() < fire_rate:
            return StrategyOrderIntent(view.stock_id, "sell", "market", min(size, position))
        return None
