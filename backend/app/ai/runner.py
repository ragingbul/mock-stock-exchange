"""AI strategy registry and runner — submits via order gateway only."""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import MarketView, StrategyOrderIntent, TraderStrategy
from app.ai.fomo import FomoStrategy
from app.ai.market_maker import MarketMakerStrategy
from app.ai.mean_reversion import MeanReversionStrategy
from app.ai.momentum import MomentumStrategy
from app.ai.noise import NoiseStrategy
from app.ai.panic import PanicStrategy
from app.ai.value_investor import ValueInvestorStrategy
from app.exchange.book_registry import books
from app.models import AIAgent, Holding, OrderSide, OrderType, Stock, Trader, TraderType
from app.schemas import TraderCreate
from app.services.trader_service import create_trader
from app.services import news_service, order_service
from app.services.market_intensity import strategy_configs
from app.services.market_model import compute_signals
from app.services.news_impact_resolver import combined_target_for_stock
from app.services.simulation_settings_service import get_or_create_settings


STRATEGIES: dict[str, type[TraderStrategy]] = {
    "market_maker": MarketMakerStrategy,
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "value_investor": ValueInvestorStrategy,
    "fomo": FomoStrategy,
    "panic": PanicStrategy,
    "noise": NoiseStrategy,
}


def build_strategy(name: str, config: dict | None = None) -> TraderStrategy:
    cls = STRATEGIES.get(name)
    if cls is None:
        raise ValueError(f"unknown strategy: {name}")
    return cls(config)


def sync_intensity_configs(db: Session) -> int:
    """Apply volatility presets to all AI agents (bootstrap + re-seed)."""
    configs = strategy_configs()
    updated = 0
    for agent in db.scalars(select(AIAgent)).all():
        if agent.strategy in configs:
            agent.config_json = json.dumps(configs[agent.strategy])
            updated += 1
    db.commit()
    return updated


def register_ai_agent(
    db: Session,
    *,
    name: str,
    strategy: str,
    capital: Decimal | None = None,
    config: dict | None = None,
) -> AIAgent:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    trader = create_trader(
        db,
        TraderCreate(name=name, trader_type=TraderType.AI, starting_capital=capital),
    )
    preset = strategy_configs().get(strategy, {})
    merged = {**preset, **(config or {})}
    agent = AIAgent(
        trader_id=trader.id,
        strategy=strategy,
        config_json=json.dumps(merged),
        capital=trader.starting_capital,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _position(db: Session, trader_id: int, stock_id: int) -> int:
    h = db.scalar(
        select(Holding).where(Holding.trader_id == trader_id, Holding.stock_id == stock_id)
    )
    return h.quantity if h else 0


def _book_pressure(book) -> tuple[float, float]:
    buy_notional = sum(float(e.price) * e.quantity for e in book.bids[:8])
    sell_notional = sum(float(e.price) * e.quantity for e in book.asks[:8])
    return buy_notional, sell_notional


def run_agent_once(db: Session, agent: AIAgent, stock: Stock) -> dict:
    trader = db.get(Trader, agent.trader_id)
    if trader is None or not agent.is_enabled:
        return {"skipped": True}
    allowed = agent.allowed_tickers
    if allowed != "*" and stock.ticker not in [t.strip() for t in allowed.split(",")]:
        return {"skipped": True, "reason": "ticker not allowed"}

    book = books.get(stock.id)
    bid = book.best_bid().price if book.best_bid() else None
    ask = book.best_ask().price if book.best_ask() else None
    news = float(news_service.news_pressure_for_ticker(db, stock.ticker))
    impact = combined_target_for_stock(db, stock)
    remaining = float(impact["remaining_impact_pct"])
    reached = bool(impact["reached"])
    settings = get_or_create_settings(db)
    strength = float(settings.news_reaction_strength)
    # Blend legacy news pressure with remaining target impact
    if not reached and remaining != 0:
        news = news + (remaining / 10.0) * strength
    buy_notional, sell_notional = _book_pressure(book)
    sentiment = max(-1.0, min(1.0, news * 0.6))
    signals = compute_signals(
        buy_notional=buy_notional,
        sell_notional=sell_notional,
        sentiment=sentiment,
        news=news,
        ai_pressure=news * 0.5,
        fair_value=stock.fair_value,
        last_price=stock.last_traded_price,
        reference_price=stock.fair_value,
    )
    ltp = float(stock.last_traded_price)
    fv = float(stock.fair_value) or float(stock.starting_price)
    prev = float(stock.previous_close) or float(stock.starting_price)
    return_vs_fv = (ltp - fv) / fv if fv else 0.0
    return_vs_prev = (ltp - prev) / prev if prev else 0.0
    recent_return = return_vs_fv * 0.75 + return_vs_prev * 0.25
    # Bias recent_return toward remaining news target when active
    if not reached:
        recent_return = recent_return * 0.4 + (remaining / 100.0) * 0.6 * strength
    view = MarketView(
        ticker=stock.ticker,
        stock_id=stock.id,
        last_price=stock.last_traded_price,
        fair_value=stock.fair_value,
        best_bid=bid,
        best_ask=ask,
        recent_return=recent_return,
        news_impact=news,
        signal=signals.signal,
        remaining_impact_pct=remaining,
        target_reached=reached,
    )
    cfg = json.loads(agent.config_json or "{}")
    # Reduce aggression once target is reached
    if reached and agent.strategy in {"fomo", "panic", "momentum"}:
        cfg["fire_rate"] = min(float(cfg.get("fire_rate", 0.5)), 0.25)
        cfg["aggressiveness"] = min(float(cfg.get("aggressiveness", 0.5)), 0.3)
    strategy = build_strategy(agent.strategy, cfg)
    position = _position(db, trader.id, stock.id)
    cash = Decimal(trader.cash)
    intent = strategy.decide(view, cash, position)
    if intent is None and not reached and remaining < -0.5 and agent.strategy in {"market_maker", "noise"}:
        sell_size = max(int(cfg.get("size", cfg.get("quote_size", 35))), 1)
        sell_size = int(sell_size * (1.0 + min(abs(remaining) / 5.0, 2.0) * strength))
        if agent.strategy == "market_maker":
            from app.services.liquidity_service import _ensure_mm_inventory

            _ensure_mm_inventory(db, trader.id, stock, sell_size)
            intent = StrategyOrderIntent(
                stock.id, "sell", "limit", sell_size, stock.last_traded_price
            )
        elif position >= sell_size:
            intent = StrategyOrderIntent(
                stock.id, "sell", "limit", sell_size, stock.last_traded_price
            )
    if intent is None:
        return {"skipped": True, "reason": "no intent"}
    if not reached and abs(remaining) > 0 and agent.strategy in {"fomo", "panic", "momentum"}:
        boost = 1.0 + min(abs(remaining) / 4.0, 3.0) * strength
        intent.quantity = max(1, int(intent.quantity * boost * float(settings.ai_aggressiveness)))
    # Prefer selling into negative remaining targets / buying into positive
    if not reached:
        if remaining < -0.5 and intent.side == "buy" and agent.strategy == "fomo":
            return {"skipped": True, "reason": "fomo suppressed by bearish target"}
        if remaining > 0.5 and intent.side == "sell" and agent.strategy == "panic":
            return {"skipped": True, "reason": "panic suppressed by bullish target"}

    side = OrderSide.BUY if intent.side == "buy" else OrderSide.SELL
    otype = OrderType.MARKET if intent.order_type == "market" else OrderType.LIMIT
    try:
        order, trades = order_service.submit_order(
            db,
            trader_id=trader.id,
            stock_id=intent.stock_id,
            side=side,
            order_type=otype,
            quantity=intent.quantity,
            price=intent.price,
        )
        return {
            "order_id": order.id,
            "stock_id": stock.id,
            "status": order.status.value,
            "trades": len(trades),
            "strategy": agent.strategy,
        }
    except order_service.OrderGatewayError as exc:
        return {"error": str(exc), "strategy": agent.strategy}


def run_all_agents(db: Session) -> list[dict]:
    agents = list(db.scalars(select(AIAgent).where(AIAgent.is_enabled.is_(True))).all())
    stocks = list(db.scalars(select(Stock).where(Stock.is_open.is_(True))).all())
    results = []
    for agent in agents:
        for stock in stocks:
            results.append(run_agent_once(db, agent, stock))
    return results


def seed_default_agents(db: Session) -> int:
    created = 0
    for strategy in STRATEGIES:
        existing = db.scalar(select(AIAgent).where(AIAgent.strategy == strategy))
        if existing:
            continue
        register_ai_agent(
            db,
            name=f"AI-{strategy}",
            strategy=strategy,
            capital=Decimal("2000000"),
        )
        created += 1
    sync_intensity_configs(db)
    return created
