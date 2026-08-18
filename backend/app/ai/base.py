"""Base interface for AI trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class MarketView:
    ticker: str
    stock_id: int
    last_price: Decimal
    fair_value: Decimal
    best_bid: Decimal | None
    best_ask: Decimal | None
    recent_return: float  # short-term %
    news_impact: float
    signal: float
    remaining_impact_pct: float = 0.0
    target_reached: bool = True


@dataclass
class StrategyOrderIntent:
    stock_id: int
    side: str  # buy/sell
    order_type: str  # market/limit
    quantity: int
    price: Decimal | None = None


class TraderStrategy(ABC):
    name: str = "base"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    def decide(self, view: MarketView, cash: Decimal, position: int) -> StrategyOrderIntent | None:
        """Return an order intent or None to skip."""
