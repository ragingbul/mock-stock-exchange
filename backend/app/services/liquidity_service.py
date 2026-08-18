"""Provision AI market-maker quotes so participant market orders can fill."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exchange.book_registry import books
from app.exchange.order_book import OrderBook
from app.models import AIAgent, OrderSide, OrderType, Stock, Trader
from app.schemas import HoldingAdjust
from app.core.config import get_settings
from app.services import order_service, portfolio_service


def _opposite_available(book: OrderBook, side: OrderSide, exclude_trader_id: int) -> int:
    entries = book.asks if side == OrderSide.BUY else book.bids
    total = 0
    for entry in entries:
        if entry.trader_id == exclude_trader_id:
            continue
        total += entry.quantity
    return total


def _market_maker_agent(db: Session) -> AIAgent | None:
    return db.scalar(
        select(AIAgent).where(
            AIAgent.strategy == "market_maker",
            AIAgent.is_enabled.is_(True),
        )
    )


def _quantize_price(price: Decimal, tick: Decimal) -> Decimal:
    if tick <= 0:
        return price
    steps = (price / tick).to_integral_value(rounding=ROUND_DOWN)
    return steps * tick


def _quote_prices(stock: Stock, spread_bps: float | None = None) -> tuple[Decimal, Decimal]:
    bps = spread_bps if spread_bps is not None else get_settings().mm_spread_bps
    mid = Decimal(stock.last_traded_price)
    half = mid * Decimal(str(bps / 10000))
    tick = Decimal(stock.tick_size)
    bid = _quantize_price(mid - half, tick)
    ask = _quantize_price(mid + half, tick)
    return bid, ask


def _ensure_mm_inventory(db: Session, trader_id: int, stock: Stock, quantity: int) -> None:
    from app.services.order_service import _holding_qty

    need = max(quantity, 1)
    have = _holding_qty(db, trader_id, stock.id)
    if have >= need:
        return
    portfolio_service.set_holding(
        db,
        trader_id,
        HoldingAdjust(
            stock_id=stock.id,
            quantity=need,
            avg_cost=Decimal(stock.last_traded_price),
        ),
    )


def provision_two_sided_quotes(
    db: Session,
    stock: Stock,
    *,
    quote_size: int | None = None,
    spread_bps: float | None = None,
) -> int:
    """Post resting bid and ask from the market-maker agent. Returns orders placed."""
    settings = get_settings()
    quote_size = quote_size if quote_size is not None else settings.mm_quote_size
    spread_bps = spread_bps if spread_bps is not None else settings.mm_spread_bps
    agent = _market_maker_agent(db)
    if agent is None:
        return 0
    trader = db.get(Trader, agent.trader_id)
    if trader is None or not trader.is_active:
        return 0

    bid, ask = _quote_prices(stock, spread_bps)
    size = max(quote_size, 1)
    placed = 0
    _ensure_mm_inventory(db, trader.id, stock, size)

    try:
        order_service.submit_order(
            db,
            trader_id=trader.id,
            stock_id=stock.id,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=size,
            price=bid,
        )
        placed += 1
    except order_service.OrderGatewayError:
        pass

    try:
        order_service.submit_order(
            db,
            trader_id=trader.id,
            stock_id=stock.id,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=size,
            price=ask,
        )
        placed += 1
    except order_service.OrderGatewayError:
        pass

    return placed


def ensure_liquidity_for_market_order(
    db: Session,
    stock: Stock,
    side: OrderSide,
    trader_id: int,
    quantity: int,
) -> None:
    """Add MM quotes on the opposite side if the book lacks depth for this trader."""
    book = books.get(stock.id)
    settings = get_settings()
    need = max(quantity, settings.mm_min_book_depth)
    if side == OrderSide.BUY:
        if _opposite_available(book, side, trader_id) >= need:
            return
        bid, ask = _quote_prices(stock)
        agent = _market_maker_agent(db)
        if agent is None:
            return
        _ensure_mm_inventory(db, agent.trader_id, stock, need)
        try:
            order_service.submit_order(
                db,
                trader_id=agent.trader_id,
                stock_id=stock.id,
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=need,
                price=ask,
            )
        except order_service.OrderGatewayError:
            pass
    else:
        if _opposite_available(book, side, trader_id) >= need:
            return
        bid, ask = _quote_prices(stock)
        agent = _market_maker_agent(db)
        if agent is None:
            return
        _ensure_mm_inventory(db, agent.trader_id, stock, need)
        try:
            order_service.submit_order(
                db,
                trader_id=agent.trader_id,
                stock_id=stock.id,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=need,
                price=bid,
            )
        except order_service.OrderGatewayError:
            pass


def seed_all_liquidity(db: Session, *, quote_size: int | None = None) -> int:
    from app.services import stock_service

    settings = get_settings()
    size = quote_size if quote_size is not None else settings.mm_quote_size
    total = 0
    for stock in stock_service.list_stocks(db):
        total += provision_two_sided_quotes(db, stock, quote_size=size)
    return total


def mm_has_two_sided_quotes(db: Session, stock: Stock) -> bool:
    """True when the market-maker already has resting bid and ask on this stock."""
    agent = _market_maker_agent(db)
    if agent is None:
        return False
    book = books.get(stock.id)
    has_bid = any(entry.trader_id == agent.trader_id for entry in book.bids)
    has_ask = any(entry.trader_id == agent.trader_id for entry in book.asks)
    return has_bid and has_ask


def seed_liquidity_if_needed(db: Session, *, quote_size: int | None = None) -> int:
    """Seed MM quotes only for stocks that lack two-sided liquidity."""
    from app.services import stock_service

    settings = get_settings()
    size = quote_size if quote_size is not None else settings.mm_quote_size
    total = 0
    for stock in stock_service.list_stocks(db):
        if mm_has_two_sided_quotes(db, stock):
            continue
        total += provision_two_sided_quotes(db, stock, quote_size=size)
    return total
