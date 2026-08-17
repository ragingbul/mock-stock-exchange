"""Stop-loss / take-profit routes."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_trader
from app.models import Trader
from app.models.conditional_order import ConditionalType
from app.realtime.ws_manager import manager
from app.schemas.orders import ConditionalCreate, ConditionalUpdate
from app.services import conditional_order_service
from app.services.conditional_order_service import ConditionalOrderError

router = APIRouter(tags=["conditionals"])


def _row_dict(row) -> dict:
    return {
        "id": row.id,
        "trader_id": row.trader_id,
        "stock_id": row.stock_id,
        "condition_type": row.condition_type.value,
        "quantity": row.quantity,
        "trigger_price": str(row.trigger_price),
        "status": row.status.value,
        "cancel_reason": row.cancel_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "triggered_at": row.triggered_at.isoformat() if row.triggered_at else None,
        "execution_price": str(row.execution_price) if row.execution_price is not None else None,
    }


@router.post("/conditionals")
async def create_conditional(
    payload: ConditionalCreate,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> dict:
    if payload.trader_id != trader.id:
        raise HTTPException(403, "trader_id does not match authenticated session")
    try:
        ctype = ConditionalType(payload.condition_type)
    except ValueError as exc:
        raise HTTPException(400, "condition_type must be stop_loss or take_profit") from exc
    try:
        row = conditional_order_service.create_conditional(
            db,
            trader_id=trader.id,
            stock_id=payload.stock_id,
            condition_type=ctype,
            quantity=payload.quantity,
            trigger_price=Decimal(payload.trigger_price),
        )
    except ConditionalOrderError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = _row_dict(row)
    await manager.broadcast("CONDITIONAL_UPDATED", data)
    return data


@router.get("/traders/{trader_id}/conditionals")
def list_conditionals(
    trader_id: int,
    active_only: bool = False,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> list[dict]:
    if trader_id != trader.id:
        raise HTTPException(403, "trader_id does not match authenticated session")
    rows = conditional_order_service.list_conditionals(
        db, trader_id=trader.id, active_only=active_only
    )
    return [_row_dict(r) for r in rows]


@router.patch("/conditionals/{conditional_id}")
async def modify_conditional(
    conditional_id: int,
    payload: ConditionalUpdate,
    trader_id: int,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> dict:
    if trader_id != trader.id:
        raise HTTPException(403, "trader_id does not match authenticated session")
    try:
        row = conditional_order_service.modify_conditional(
            db,
            conditional_id,
            trader_id=trader.id,
            quantity=payload.quantity,
            trigger_price=payload.trigger_price,
        )
    except ConditionalOrderError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = _row_dict(row)
    await manager.broadcast("CONDITIONAL_UPDATED", data)
    return data


@router.delete("/conditionals/{conditional_id}")
async def cancel_conditional(
    conditional_id: int,
    trader_id: int,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> dict:
    if trader_id != trader.id:
        raise HTTPException(403, "trader_id does not match authenticated session")
    try:
        row = conditional_order_service.cancel_conditional(
            db, conditional_id, trader_id=trader.id
        )
    except ConditionalOrderError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = _row_dict(row)
    await manager.broadcast("CONDITIONAL_UPDATED", data)
    return data
