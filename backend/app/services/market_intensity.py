"""Central presets for event-style market volatility (news + AI reactions)."""

from __future__ import annotations

from app.core.config import get_settings


def strategy_configs() -> dict[str, dict]:
    """Per-strategy knobs — larger sizes, weaker stabilizers, faster reactions."""
    m = get_settings().market_intensity_multiplier
    spread = get_settings().mm_spread_bps
    quote = get_settings().mm_quote_size
    size = int(round(40 * m))
    big = int(round(120 * m))
    return {
        "momentum": {
            "threshold": 0.001,
            "size": big,
            "aggressiveness": 0.98,
        },
        "mean_reversion": {
            # Wide band — lets prices run before counter-trading kicks in
            "band": 0.15,
            "size": size,
        },
        "value_investor": {
            "buy_discount": 0.20,
            "sell_premium": 0.25,
            "size": int(round(35 * m)),
        },
        "fomo": {
            "size": big,
            "news_threshold": 0.05,
            "return_threshold": 0.002,
            "signal_threshold": 0.04,
            "fire_rate": 0.96,
        },
        "panic": {
            "size": big,
            "news_threshold": -0.05,
            "return_threshold": -0.002,
            "signal_threshold": -0.04,
            "fire_rate": 0.96,
        },
        "noise": {
            "size": int(round(30 * m)),
            "trade_rate": 0.55,
        },
        "market_maker": {
            "spread_bps": spread,
            "quote_size": quote,
            "max_position": 1200,
        },
    }
