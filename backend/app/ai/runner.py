"""AI strategy registry and runner — submits via order gateway only."""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import MarketView, TraderStrategy
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
from app.services.market_model import compute_signals



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
    agent = AIAgent(
        trader_id=trader.id,
        strategy=strategy,
        config_json=json.dumps(config or {}),
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
    signals = compute_signals(
        buy_notional=0,
        sell_notional=0,
        sentiment=0.0,
        news=news,
        ai_pressure=0.0,
        fair_value=stock.fair_value,
        last_price=stock.last_traded_price,
        reference_price=stock.fair_value,
    )
    prev = float(stock.previous_close) or float(stock.starting_price)
    recent_return = (float(stock.last_traded_price) - prev) / prev if prev else 0.0
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
    )
    strategy = build_strategy(agent.strategy, json.loads(agent.config_json or "{}"))
    intent = strategy.decide(view, Decimal(trader.cash), _position(db, trader.id, stock.id))
    if intent is None:
        return {"skipped": True, "reason": "no intent"}

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
    return created
