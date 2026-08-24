"""Order gateway: validate → price at LTP → direct fill (no order book).

Layers:
  1. Validate trader / stock / session / cash / holdings
  2. Lock execution price to current last traded price
  3. Fill immediately against the exchange house account
  4. Commit
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.exchange.matching_engine import MatchFill
from app.exchange.settlement import SettlementError, settle_fill
from app.models import Holding, Order, OrderSide, OrderStatus, OrderType, Stock, Trade, Trader
from app.models.enums import MarketSessionStatus, TraderType
from app.models.market_session import MarketSession

EXCHANGE_NAME = "EXCHANGE"
EXCHANGE_CASH = Decimal("999999999999.00")
EXCHANGE_SHARES = 1_000_000_000


class OrderGatewayError(Exception):
    def __init__(self, message: str, *, rejected_order: Order | None = None) -> None:
        super().__init__(message)
        self.rejected_order = rejected_order


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


def _get_or_create_holding(db: Session, trader_id: int, stock_id: int) -> Holding:
    holding = db.scalar(
        select(Holding).where(Holding.trader_id == trader_id, Holding.stock_id == stock_id)
    )
    if holding is None:
        holding = Holding(
            trader_id=trader_id,
            stock_id=stock_id,
            quantity=0,
            avg_cost=Decimal("0"),
        )
        db.add(holding)
        db.flush()
    return holding


def _get_or_create_exchange(db: Session, stock_id: int) -> Trader:
    """Infinite counterparty for direct fills — never rests on a book."""
    exchange = db.scalar(select(Trader).where(Trader.name == EXCHANGE_NAME).limit(1))
    if exchange is None:
        exchange = Trader(
            name=EXCHANGE_NAME,
            trader_type=TraderType.AI,
            starting_capital=EXCHANGE_CASH,
            cash=EXCHANGE_CASH,
            cash_blocked_ipo=Decimal("0"),
            realized_pnl=Decimal("0"),
            is_active=True,
        )
        db.add(exchange)
        db.flush()

    exchange.cash = max(Decimal(exchange.cash), EXCHANGE_CASH)
    exchange.is_active = True
    holding = _get_or_create_holding(db, exchange.id, stock_id)
    if holding.quantity < EXCHANGE_SHARES:
        holding.quantity = EXCHANGE_SHARES
    return exchange


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
            trader_id=trader_id,
            stock_id=stock_id,
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

    # --- Layer 1: validate ---
    if trader is None or not trader.is_active:
        raise OrderGatewayError("trader not found or inactive")
    if stock is None:
        raise OrderGatewayError("stock not found")
    if quantity <= 0:
        order = reject("quantity must be positive")
        raise OrderGatewayError("quantity must be positive", rejected_order=order)

    session = _active_session(db)
    from app.models.enums import SimulationStatus, StockStatus
    from app.services.simulation_clock import get_or_create_state

    sim = get_or_create_state(db)
    if sim.status != SimulationStatus.RUNNING:
        order = reject(f"simulation is {sim.status.value}")
        raise OrderGatewayError(f"simulation is {sim.status.value}", rejected_order=order)
    if session and session.status in {MarketSessionStatus.PAUSED, MarketSessionStatus.CLOSED}:
        order = reject(f"market is {session.status.value}")
        raise OrderGatewayError(f"market is {session.status.value}", rejected_order=order)
    if getattr(stock, "status", StockStatus.ACTIVE.value) == StockStatus.DISSOLVED.value:
        order = reject("stock is dissolved")
        raise OrderGatewayError("stock is dissolved", rejected_order=order)
    if not stock.is_open or stock.is_halted:
        order = reject("stock is closed or halted")
        raise OrderGatewayError("stock is closed or halted", rejected_order=order)

    # --- Layer 2: execution price (always LTP; ignore book / opposing quotes) ---
    exec_price = Decimal(stock.last_traded_price)
    if exec_price <= 0:
        exec_price = Decimal(stock.starting_price)
    exec_price = _quantize_price(exec_price, Decimal(stock.tick_size or "0.05"))
    if exec_price <= 0:
        order = reject("invalid market price")
        raise OrderGatewayError("invalid market price", rejected_order=order)

    if side == OrderSide.BUY:
        if trader.cash < exec_price * quantity:
            order = reject("insufficient cash")
            raise OrderGatewayError("insufficient cash", rejected_order=order)
        current_qty = _holding_qty(db, trader_id, stock_id)
        max_pos = settings.max_position_per_stock
        if current_qty + quantity > max_pos:
            order = reject(f"max position is {max_pos} shares per stock")
            raise OrderGatewayError(
                f"max position is {max_pos} shares per stock", rejected_order=order
            )
    else:
        if _holding_qty(db, trader_id, stock_id) < quantity:
            order = reject("insufficient holdings (short selling disabled)")
            raise OrderGatewayError(
                "insufficient holdings (short selling disabled)", rejected_order=order
            )

    # --- Layer 3: direct fill vs exchange house ---
    exchange = _get_or_create_exchange(db, stock_id)

    user_order = Order(
        trader_id=trader_id,
        stock_id=stock_id,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        remaining_quantity=quantity,
        price=None,
        status=OrderStatus.OPEN,
        client_order_id=client_order_id,
    )
    db.add(user_order)
    db.flush()

    counter_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
    house_order = Order(
        trader_id=exchange.id,
        stock_id=stock_id,
        side=counter_side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        remaining_quantity=quantity,
        price=None,
        status=OrderStatus.OPEN,
        client_order_id=f"house-{user_order.id}",
    )
    db.add(house_order)
    db.flush()

    if side == OrderSide.BUY:
        fill = MatchFill(
            buy_order_id=user_order.id,
            sell_order_id=house_order.id,
            buyer_id=trader_id,
            seller_id=exchange.id,
            price=exec_price,
            quantity=quantity,
        )
    else:
        fill = MatchFill(
            buy_order_id=house_order.id,
            sell_order_id=user_order.id,
            buyer_id=exchange.id,
            seller_id=trader_id,
            price=exec_price,
            quantity=quantity,
        )

    trades: list[Trade] = []
    try:
        trades.append(settle_fill(db, stock_id, fill))
    except SettlementError as exc:
        db.rollback()
        raise OrderGatewayError(f"settlement failed: {exc}") from exc

    user_order.remaining_quantity = 0
    user_order.status = OrderStatus.FILLED
    house_order.remaining_quantity = 0
    house_order.status = OrderStatus.FILLED

    # --- Layer 4: commit ---
    db.commit()
    db.refresh(user_order)
    for t in trades:
        db.refresh(t)

    if side == OrderSide.SELL:
        try:
            from app.services import conditional_order_service

            conditional_order_service.cancel_for_position_closed(db, trader_id, stock_id)
        except Exception:
            pass

    _ = settings  # circuit settings retained for future knobs
    return user_order, trades


def cancel_order(db: Session, order_id: int, trader_id: int | None = None) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise OrderGatewayError("order not found")
    if trader_id is not None and order.trader_id != trader_id:
        raise OrderGatewayError("cannot cancel another trader's order")
    if order.status not in {OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED}:
        raise OrderGatewayError(f"cannot cancel order in status {order.status.value}")

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
