"""Atomic settlement of matched trades."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Holding, Order, OrderStatus, Stock, Trade, Trader
from app.exchange.matching_engine import MatchFill


class SettlementError(Exception):
    pass


def _get_or_create_holding(db: Session, trader_id: int, stock_id: int) -> Holding:
    holding = db.scalar(
        select(Holding).where(
            Holding.trader_id == trader_id, Holding.stock_id == stock_id
        )
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


def settle_fill(db: Session, stock_id: int, fill: MatchFill) -> Trade:
    """Apply one fill atomically within the caller's transaction."""
    if fill.quantity <= 0:
        raise SettlementError("fill quantity must be positive")
    if fill.price <= 0:
        raise SettlementError("fill price must be positive")
    if fill.buyer_id == fill.seller_id:
        raise SettlementError("buyer and seller must differ")

    buyer = db.get(Trader, fill.buyer_id)
    seller = db.get(Trader, fill.seller_id)
    stock = db.get(Stock, stock_id)
    buy_order = db.get(Order, fill.buy_order_id)
    sell_order = db.get(Order, fill.sell_order_id)

    if not all([buyer, seller, stock, buy_order, sell_order]):
        raise SettlementError("missing entities for settlement")

    from app.services.simulation_settings_service import get_or_create_settings

    settings = get_or_create_settings(db)
    prev_ltp = Decimal(stock.last_traded_price or stock.starting_price)
    exec_price = fill.price
    max_move = Decimal(str(settings.max_price_move_per_tick_pct)) / Decimal("100")
    if prev_ltp > 0 and max_move > 0:
        upper = prev_ltp * (Decimal("1") + max_move)
        lower = prev_ltp * (Decimal("1") - max_move)
        exec_price = max(lower, min(upper, exec_price))
    exec_price = max(Decimal("1"), min(Decimal("10000"), exec_price))
    notional = exec_price * fill.quantity

    if buyer.cash < notional:
        raise SettlementError("buyer has insufficient cash at settlement")

    seller_holding = _get_or_create_holding(db, seller.id, stock_id)
    if seller_holding.quantity < fill.quantity:
        raise SettlementError("seller has insufficient shares at settlement")

    # Transfer cash
    buyer.cash -= notional
    seller.cash += notional

    # Transfer shares — seller
    seller_holding.quantity -= fill.quantity
    # Realized PnL on seller for sold shares
    cost = seller_holding.avg_cost * fill.quantity
    proceeds = notional
    seller.realized_pnl += proceeds - cost
    if seller_holding.quantity == 0:
        seller_holding.avg_cost = Decimal("0")

    # Transfer shares — buyer (weighted average cost)
    buyer_holding = _get_or_create_holding(db, buyer.id, stock_id)
    old_qty = buyer_holding.quantity
    old_cost = buyer_holding.avg_cost * old_qty
    new_qty = old_qty + fill.quantity
    buyer_holding.quantity = new_qty
    buyer_holding.avg_cost = (
        (old_cost + notional) / new_qty if new_qty > 0 else Decimal("0")
    )

    # Update order remaining quantities / status
    for order, is_buy in ((buy_order, True), (sell_order, False)):
        order.remaining_quantity -= fill.quantity
        if order.remaining_quantity < 0:
            raise SettlementError("order remaining went negative")
        if order.remaining_quantity == 0:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

    trade = Trade(
        stock_id=stock_id,
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        buyer_id=fill.buyer_id,
        seller_id=fill.seller_id,
        quantity=fill.quantity,
        price=exec_price,
    )
    db.add(trade)
    db.flush()
    stock.last_traded_price = exec_price
    return trade
