"""Conditional stop-loss / take-profit orders — execute via existing order gateway."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Holding, OrderSide, OrderType, Stock, Trader
from app.models.conditional_order import (
    ConditionalOrder,
    ConditionalStatus,
    ConditionalType,
)
from app.services import order_service


class ConditionalOrderError(Exception):
    pass


def _holding_qty(db: Session, trader_id: int, stock_id: int) -> int:
    h = db.scalar(
        select(Holding).where(Holding.trader_id == trader_id, Holding.stock_id == stock_id)
    )
    return h.quantity if h else 0


def _active_qty_reserved(db: Session, trader_id: int, stock_id: int, exclude_id: int | None = None) -> int:
    stmt = select(ConditionalOrder).where(
        ConditionalOrder.trader_id == trader_id,
        ConditionalOrder.stock_id == stock_id,
        ConditionalOrder.status == ConditionalStatus.ACTIVE,
    )
    rows = list(db.scalars(stmt).all())
    total = 0
    for row in rows:
        if exclude_id is not None and row.id == exclude_id:
            continue
        total += row.quantity
    return total


def create_conditional(
    db: Session,
    *,
    trader_id: int,
    stock_id: int,
    condition_type: ConditionalType,
    quantity: int,
    trigger_price: Decimal,
) -> ConditionalOrder:
    trader = db.get(Trader, trader_id)
    stock = db.get(Stock, stock_id)
    if trader is None or stock is None:
        raise ConditionalOrderError("trader or stock not found")
    if quantity <= 0:
        raise ConditionalOrderError("quantity must be positive")
    if trigger_price <= 0:
        raise ConditionalOrderError("trigger price must be positive")

    held = _holding_qty(db, trader_id, stock_id)
    reserved = _active_qty_reserved(db, trader_id, stock_id)
    if quantity > held - reserved:
        raise ConditionalOrderError(
            f"not enough shares (held={held}, reserved={reserved}, requested={quantity})"
        )

    ltp = Decimal(stock.last_traded_price)
    if condition_type == ConditionalType.STOP_LOSS and trigger_price >= ltp:
        raise ConditionalOrderError("stop loss must be below current price")
    if condition_type == ConditionalType.TAKE_PROFIT and trigger_price <= ltp:
        raise ConditionalOrderError("take profit must be above current price")

    row = ConditionalOrder(
        trader_id=trader_id,
        stock_id=stock_id,
        condition_type=condition_type,
        quantity=quantity,
        trigger_price=trigger_price,
        status=ConditionalStatus.ACTIVE,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def cancel_conditional(
    db: Session,
    conditional_id: int,
    *,
    trader_id: int | None = None,
    reason: str = "cancelled by user",
) -> ConditionalOrder:
    row = db.get(ConditionalOrder, conditional_id)
    if row is None:
        raise ConditionalOrderError("conditional order not found")
    if trader_id is not None and row.trader_id != trader_id:
        raise ConditionalOrderError("not your conditional order")
    if row.status != ConditionalStatus.ACTIVE:
        raise ConditionalOrderError(f"cannot cancel status={row.status.value}")
    row.status = ConditionalStatus.CANCELLED
    row.cancel_reason = reason
    db.commit()
    db.refresh(row)
    return row


def modify_conditional(
    db: Session,
    conditional_id: int,
    *,
    trader_id: int,
    quantity: int | None = None,
    trigger_price: Decimal | None = None,
) -> ConditionalOrder:
    row = db.get(ConditionalOrder, conditional_id)
    if row is None or row.trader_id != trader_id:
        raise ConditionalOrderError("conditional order not found")
    if row.status != ConditionalStatus.ACTIVE:
        raise ConditionalOrderError("only active conditionals can be modified")

    new_qty = quantity if quantity is not None else row.quantity
    new_price = trigger_price if trigger_price is not None else row.trigger_price
    if new_qty <= 0 or new_price <= 0:
        raise ConditionalOrderError("invalid quantity or price")

    held = _holding_qty(db, trader_id, row.stock_id)
    reserved = _active_qty_reserved(db, trader_id, row.stock_id, exclude_id=row.id)
    if new_qty > held - reserved:
        raise ConditionalOrderError("not enough shares for new quantity")

    row.quantity = new_qty
    row.trigger_price = new_price
    db.commit()
    db.refresh(row)
    return row


def list_conditionals(
    db: Session,
    *,
    trader_id: int,
    active_only: bool = False,
) -> list[ConditionalOrder]:
    stmt = select(ConditionalOrder).where(ConditionalOrder.trader_id == trader_id)
    if active_only:
        stmt = stmt.where(ConditionalOrder.status == ConditionalStatus.ACTIVE)
    return list(db.scalars(stmt.order_by(ConditionalOrder.id.desc())).all())


def cancel_for_position_closed(db: Session, trader_id: int, stock_id: int) -> list[ConditionalOrder]:
    """Cancel or shrink conditionals when holdings drop after a sell."""
    held = _holding_qty(db, trader_id, stock_id)
    rows = list(
        db.scalars(
            select(ConditionalOrder).where(
                ConditionalOrder.trader_id == trader_id,
                ConditionalOrder.stock_id == stock_id,
                ConditionalOrder.status == ConditionalStatus.ACTIVE,
            )
        ).all()
    )
    changed: list[ConditionalOrder] = []
    if held <= 0:
        for row in rows:
            row.status = ConditionalStatus.CANCELLED
            row.cancel_reason = "Position closed"
            changed.append(row)
    else:
        # Shrink if reserved exceeds holdings (FIFO by id)
        remaining = held
        for row in sorted(rows, key=lambda r: r.id):
            if remaining <= 0:
                row.status = ConditionalStatus.CANCELLED
                row.cancel_reason = "Position closed"
                changed.append(row)
            elif row.quantity > remaining:
                row.quantity = remaining
                remaining = 0
                changed.append(row)
            else:
                remaining -= row.quantity
    if changed:
        db.commit()
    return changed


def evaluate_conditionals_for_stock(db: Session, stock_id: int) -> list[dict]:
    """Trigger active SL/TP when LTP crosses thresholds. Returns event payloads."""
    stock = db.get(Stock, stock_id)
    if stock is None:
        return []
    ltp = Decimal(stock.last_traded_price)
    rows = list(
        db.scalars(
            select(ConditionalOrder).where(
                ConditionalOrder.stock_id == stock_id,
                ConditionalOrder.status == ConditionalStatus.ACTIVE,
            )
        ).all()
    )
    events: list[dict] = []
    for row in rows:
        should = False
        if row.condition_type == ConditionalType.STOP_LOSS and ltp <= row.trigger_price:
            should = True
        if row.condition_type == ConditionalType.TAKE_PROFIT and ltp >= row.trigger_price:
            should = True
        if not should:
            continue

        held = _holding_qty(db, row.trader_id, stock_id)
        qty = min(row.quantity, held)
        if qty <= 0:
            row.status = ConditionalStatus.CANCELLED
            row.cancel_reason = "Position closed"
            db.commit()
            continue

        try:
            order, trades = order_service.submit_order(
                db,
                trader_id=row.trader_id,
                stock_id=stock_id,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=qty,
            )
        except order_service.OrderGatewayError as exc:
            events.append(
                {
                    "event": "CONDITIONAL_FAILED",
                    "conditional_id": row.id,
                    "trader_id": row.trader_id,
                    "detail": str(exc),
                }
            )
            continue

        avg = None
        if trades:
            notional = sum((t.price * t.quantity for t in trades), Decimal("0"))
            filled = sum(t.quantity for t in trades)
            avg = (notional / filled) if filled else None

        row.status = ConditionalStatus.TRIGGERED
        row.triggered_at = datetime.now(timezone.utc)
        row.execution_price = avg
        row.linked_order_id = order.id
        db.commit()

        label = (
            "STOP LOSS TRIGGERED"
            if row.condition_type == ConditionalType.STOP_LOSS
            else "TAKE PROFIT TRIGGERED"
        )
        events.append(
            {
                "event": (
                    "STOP_LOSS_TRIGGERED"
                    if row.condition_type == ConditionalType.STOP_LOSS
                    else "TAKE_PROFIT_TRIGGERED"
                ),
                "message": (
                    f"{label}\n{stock.ticker}\n{qty} shares\n"
                    f"{'Trigger' if row.condition_type == ConditionalType.STOP_LOSS else 'Target'}: ₹{row.trigger_price}\n"
                    f"Execution Price: ₹{avg if avg is not None else '—'}"
                ),
                "conditional_id": row.id,
                "trader_id": row.trader_id,
                "stock_id": stock_id,
                "ticker": stock.ticker,
                "quantity": qty,
                "trigger_price": str(row.trigger_price),
                "execution_price": str(avg) if avg is not None else None,
                "condition_type": row.condition_type.value,
            }
        )
        # Position may have changed — clean leftovers
        cancel_for_position_closed(db, row.trader_id, stock_id)
    return events
