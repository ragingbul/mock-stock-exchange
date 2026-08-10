"""Configurable mathematical market model.

Influences AI expectations / reference price — NEVER overwrites last traded price.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import random

from app.core.config import get_settings


@dataclass
class MarketForceWeights:
    wp: float = 0.40  # order pressure
    ws: float = 0.25  # sentiment
    wn: float = 0.20  # news
    wa: float = 0.15  # AI pressure


@dataclass
class MarketSignals:
    order_pressure: float  # P in [-1, 1]
    sentiment: float  # S in [-1, 1]
    news: float  # N in [-1, 1]
    ai_pressure: float  # A in [-1, 1]
    combined_force: float  # M
    signal: float  # M + noise
    fair_value_correction: float
    reference_price: Decimal


def order_pressure(buy_notional: float, sell_notional: float) -> float:
    denom = buy_notional + sell_notional
    if denom <= 0:
        return 0.0
    return (buy_notional - sell_notional) / denom


def combined_force(
    p: float,
    s: float,
    n: float,
    a: float,
    weights: MarketForceWeights | None = None,
) -> float:
    w = weights or MarketForceWeights()
    return w.wp * p + w.ws * s + w.wn * n + w.wa * a


def fair_value_correction(fair_value: Decimal, price: Decimal, alpha: float = 0.02) -> float:
    return alpha * float(fair_value - price)


def update_reference_price(
    reference: Decimal, m: float, k: float = 0.01
) -> Decimal:
    """ReferencePrice(t+1) = ReferencePrice(t) * (1 + k*M)."""
    factor = Decimal(str(1.0 + k * m))
    return (reference * factor).quantize(Decimal("0.0001"))


def compute_signals(
    *,
    buy_notional: float,
    sell_notional: float,
    sentiment: float,
    news: float,
    ai_pressure: float,
    fair_value: Decimal,
    last_price: Decimal,
    reference_price: Decimal,
    weights: MarketForceWeights | None = None,
    noise_std: float | None = None,
    rng: random.Random | None = None,
) -> MarketSignals:
    settings = get_settings()
    rng = rng or random.Random(settings.random_seed)
    w = weights or MarketForceWeights(wn=settings.market_news_weight)
    p = order_pressure(buy_notional, sell_notional)
    m = combined_force(p, sentiment, news, ai_pressure, w)
    std = noise_std if noise_std is not None else settings.market_noise_std
    noise = rng.uniform(-std, std)
    signal = m + noise
    correction = fair_value_correction(fair_value, last_price)
    new_ref = update_reference_price(reference_price, m)
    return MarketSignals(
        order_pressure=p,
        sentiment=sentiment,
        news=news,
        ai_pressure=ai_pressure,
        combined_force=m,
        signal=signal,
        fair_value_correction=correction,
        reference_price=new_ref,
    )
