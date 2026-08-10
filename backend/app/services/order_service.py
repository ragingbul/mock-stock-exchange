"""Order gateway: validate → persist → match → settle."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.exchange.book_registry import books
from app.exchange.matching_engine import MatchingEngine
from app.exchange.settlement import SettlementError, settle_fill
from app.models import Holding, Order, OrderSide, OrderStatus, OrderType, Stock, Trade, Trader
from app.models.enums import MarketSessionStatus
from app.models.market_session import MarketSession
from app.services import liquidity_service


class OrderGatewayError(Exception):
    def __init__(self, message: str, *, rejected_order: Order | None = None) -> None:
        super().__init__(message)
        self.rejected_order = rejected_order


engine = MatchingEngine()


def _quantize_price(price: Decimal, tick: Decimal) -> Decimal:
    if tick <= 0:
        return price
    steps = (price / tick).to_integral_value(rounding=ROUND_DOWN)
    return steps * tick


def _active_session(db: Session) -> MarketSession | None:
    return db.scalar(select(MarketSession).order_by(MarketSession.id.desc()).limit(1))


def _holding_qty(db: Session, trader_id: int, stock_id: int) -> int:
    h = db.scalar(
        select(Holding).where(Holding.trader_id == trader_id, Holding.stock_id == stock_id)
    )
    return h.quantity if h else 0


def submit_order(
    db: Session,
    *,
    trader_id: int,
    stock_id: int,
    side: OrderSide,
    order_type: OrderType,
    quantity: int,
    price: Decimal | None = None,
    client_order_id: str | None = None,
) -> tuple[Order, list[Trade]]:
    settings = get_settings()
    trader = db.get(Trader, trader_id)
    stock = db.get(Stock, stock_id)

    def reject(reason: str) -> Order:
        order = Order(
            trader_id=trader_id if trader else trader_id,
            stock_id=stock_id if stock else stock_id,
            side=side,
            order_type=order_type,
            quantity=max(quantity, 0),
            remaining_quantity=0,
            price=price,
            status=OrderStatus.REJECTED,
            reject_reason=reason,
            client_order_id=client_order_id,
        )
        if trader and stock:
            db.add(order)
            db.commit()
            db.refresh(order)
        return order

    if trader is None or not trader.is_active:
        raise OrderGatewayError("trader not found or inactive")
    if stock is None:
        raise OrderGatewayError("stock not found")
    if quantity <= 0:
        order = reject("quantity must be positive")
        raise OrderGatewayError("quantity must be positive", rejected_order=order)
    if order_type == OrderType.LIMIT and (price is None or price <= 0):
        order = reject("limit order requires positive price")
        raise OrderGatewayError("limit order requires positive price", rejected_order=order)

    session = _active_session(db)
    if session and session.status in {MarketSessionStatus.PAUSED, MarketSessionStatus.CLOSED}:
        order = reject(f"market is {session.status.value}")
        raise OrderGatewayError(f"market is {session.status.value}", rejected_order=order)
    if not stock.is_open or stock.is_halted:
        order = reject("stock is closed or halted")
        raise OrderGatewayError("stock is closed or halted", rejected_order=order)

    circuit = Decimal(str(settings.default_circuit_pct))
    ref = Decimal(stock.previous_close)
    if order_type == OrderType.LIMIT and price is not None and ref > 0:
        upper = ref * (Decimal("1") + circuit)
        lower = ref * (Decimal("1") - circuit)
        if price > upper or price < lower:
            order = reject("price outside circuit limits")
            raise OrderGatewayError("price outside circuit limits", rejected_order=order)

    if order_type == OrderType.LIMIT and price is not None:
        price = _quantize_price(price, Decimal(stock.tick_size))

    if side == OrderSide.BUY:
        book = books.get(stock_id)
        if order_type == OrderType.MARKET:
            best_ask = book.best_ask()
            est_price = best_ask.price if best_ask else Decimal(stock.last_traded_price)
        else:
            est_price = price if order_type == OrderType.LIMIT else Decimal(stock.last_traded_price)
        if est_price and trader.cash < est_price * quantity:
            order = reject("insufficient cash")
            raise OrderGatewayError("insufficient cash", rejected_order=order)
    else:
        if _holding_qty(db, trader_id, stock_id) < quantity:
            order = reject("insufficient holdings (short selling disabled)")
            raise OrderGatewayError(
                "insufficient holdings (short selling disabled)", rejected_order=order
            )

    if order_type == OrderType.MARKET:
        liquidity_service.ensure_liquidity_for_market_order(
            db, stock, side, trader_id, quantity
        )

    order = Order(
        trader_id=trader_id,
        stock_id=stock_id,
        side=side,
        order_type=order_type,
        quantity=quantity,
        remaining_quantity=quantity,
        price=price,
        status=OrderStatus.OPEN,
        client_order_id=client_order_id,
    )
    db.add(order)
    db.flush()

    book = books.get(stock_id)
    result = engine.match(
        book,
        order_id=order.id,
        trader_id=trader_id,
        side=side,
        order_type=order_type,
        quantity=quantity,
        limit_price=price,
    )

    trades: list[Trade] = []
    try:
        for fill in result.fills:
            trades.append(settle_fill(db, stock_id, fill))
    except SettlementError as exc:
        db.rollback()
        books.get(stock_id).remove_order(order.id)
        raise OrderGatewayError(f"settlement failed: {exc}") from exc

    filled_qty = sum(t.quantity for t in trades)

    if order_type == OrderType.MARKET:
        # Market leftovers are never booked.
        order.remaining_quantity = 0
        if filled_qty == 0:
            order.status = OrderStatus.CANCELLED
            order.reject_reason = "no liquidity"
        elif filled_qty < order.quantity:
            order.status = OrderStatus.PARTIALLY_FILLED
        else:
            order.status = OrderStatus.FILLED
    else:
        order.remaining_quantity = result.remaining_quantity
        if filled_qty == 0 and result.resting:
            order.status = OrderStatus.OPEN
        elif result.remaining_quantity == 0:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

    db.commit()
    db.refresh(order)
    for t in trades:
        db.refresh(t)
    return order, trades


def cancel_order(db: Session, order_id: int, trader_id: int | None = None) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise OrderGatewayError("order not found")
    if trader_id is not None and order.trader_id != trader_id:
        raise OrderGatewayError("cannot cancel another trader's order")
    if order.status not in {OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED}:
        raise OrderGatewayError(f"cannot cancel order in status {order.status.value}")

    books.get(order.stock_id).remove_order(order.id)
    order.status = OrderStatus.CANCELLED
    order.remaining_quantity = 0
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> Order | None:
    return db.get(Order, order_id)


def list_orders(
    db: Session,
    *,
    trader_id: int | None = None,
    stock_id: int | None = None,
    open_only: bool = False,
) -> list[Order]:
    stmt = select(Order).order_by(Order.id.desc())
    if trader_id is not None:
        stmt = stmt.where(Order.trader_id == trader_id)
    if stock_id is not None:
        stmt = stmt.where(Order.stock_id == stock_id)
    if open_only:
        stmt = stmt.where(
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
        )
    return list(db.scalars(stmt).all())


def list_trades(
    db: Session,
    *,
    stock_id: int | None = None,
    trader_id: int | None = None,
    limit: int = 100,
) -> list[Trade]:
    stmt = select(Trade).order_by(Trade.id.desc()).limit(limit)
    if stock_id is not None:
        stmt = stmt.where(Trade.stock_id == stock_id)
    if trader_id is not None:
        stmt = stmt.where((Trade.buyer_id == trader_id) | (Trade.seller_id == trader_id))
    return list(db.scalars(stmt).all())
