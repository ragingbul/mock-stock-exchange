"""Value investor — conservative fair-value buys/sells."""

from __future__ import annotations

from decimal import Decimal

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy


class ValueInvestorStrategy(TraderStrategy):
    name = "value_investor"

    def decide(self, view: MarketView, cash: Decimal, position: int) -> StrategyOrderIntent | None:
        discount = float(self.config.get("buy_discount", 0.18))
        premium = float(self.config.get("sell_premium", 0.22))
        size = int(self.config.get("size", 35))
        if view.fair_value <= 0:
            return None
        gap = float((view.last_price - view.fair_value) / view.fair_value)
        if gap < -discount and cash > view.last_price * size:
            px = view.last_price * Decimal("0.995")
            return StrategyOrderIntent(view.stock_id, "buy", "limit", size, px)
        if gap > premium and position >= size:
            px = view.last_price * Decimal("1.005")
            return StrategyOrderIntent(view.stock_id, "sell", "limit", size, px)
        return None
