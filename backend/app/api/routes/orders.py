"""Order and market-data routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_trader
from app.exchange.book_registry import books
from app.models import Trader
from app.models import Stock
from app.realtime.ws_manager import manager
from app.schemas.orders import OrderBookRead, OrderCreate, OrderRead, TradeRead
from app.services import order_service
from app.services.execution_summary import build_execution_summary, human_reason
from app.services.order_service import OrderGatewayError

router = APIRouter(tags=["orders"])


@router.post("/orders", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> dict:
    if payload.trader_id != trader.id:
        raise HTTPException(status_code=403, detail="trader_id does not match authenticated session")
    try:
        order, trades = order_service.submit_order(
            db,
            trader_id=trader.id,
            stock_id=payload.stock_id,
            side=payload.side,
            order_type=payload.order_type,
            quantity=payload.quantity,
            price=payload.price,
            client_order_id=payload.client_order_id,
        )
    except OrderGatewayError as exc:
        if exc.rejected_order is not None:
            stock = db.get(Stock, exc.rejected_order.stock_id)
            summary = build_execution_summary(exc.rejected_order, [], stock)
            return {
                "order": OrderRead.model_validate(exc.rejected_order).model_dump(mode="json"),
                "trades": [],
                "rejected": True,
                "executed": False,
                "detail": str(exc),
                "execution_summary": summary,
            }
        raise HTTPException(status_code=400, detail=human_reason(str(exc))) from exc

    stock = db.get(Stock, order.stock_id)
    trade_payload = [TradeRead.model_validate(t).model_dump(mode="json") for t in trades]
    summary = build_execution_summary(order, trades, stock)
    await manager.broadcast(
        "TRADE_EXECUTED" if trades else "ORDER_BOOK_UPDATED",
        {
            "order_id": order.id,
            "stock_id": order.stock_id,
            "trades": trade_payload,
            "book": books.get(order.stock_id).depth(),
        },
    )
    await manager.broadcast(
        "PRICE_UPDATED",
        {"stock_id": order.stock_id, "trades": trade_payload},
    )
    await manager.broadcast(
        "PORTFOLIO_UPDATED",
        {"trader_id": trader.id, "stock_id": order.stock_id},
    )
    await manager.broadcast("WALLET_UPDATED", {"trader_id": trader.id})

    # Evaluate stop-loss / take-profit after price moves
    if trades:
        from app.services import conditional_order_service

        for ev in conditional_order_service.evaluate_conditionals_for_stock(db, order.stock_id):
            await manager.broadcast(ev.get("event", "CONDITIONAL_UPDATED"), ev)
            if ev.get("trader_id"):
                await manager.broadcast("WALLET_UPDATED", {"trader_id": ev["trader_id"]})
                await manager.broadcast("PORTFOLIO_UPDATED", {"trader_id": ev["trader_id"]})

    return {
        "order": OrderRead.model_validate(order).model_dump(mode="json"),
        "trades": trade_payload,
        "rejected": False,
        "executed": summary["executed"],
        "execution_summary": summary,
    }


@router.delete("/orders/{order_id}", response_model=OrderRead)
async def cancel_order(
    order_id: int,
    trader_id: int | None = None,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> OrderRead:
    if trader_id is not None and trader_id != trader.id:
        raise HTTPException(status_code=403, detail="trader_id does not match authenticated session")
    try:
        order = order_service.cancel_order(db, order_id, trader_id=trader.id)
    except OrderGatewayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await manager.broadcast(
        "ORDER_BOOK_UPDATED",
        {"stock_id": order.stock_id, "book": books.get(order.stock_id).depth()},
    )
    return OrderRead.model_validate(order)


@router.get("/orders", response_model=list[OrderRead])
def list_orders(
    trader_id: int | None = None,
    stock_id: int | None = None,
    open_only: bool = False,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> list[OrderRead]:
    if trader_id is not None and trader_id != trader.id:
        raise HTTPException(status_code=403, detail="trader_id does not match authenticated session")
    return [
        OrderRead.model_validate(o)
        for o in order_service.list_orders(
            db, trader_id=trader.id, stock_id=stock_id, open_only=open_only
        )
    ]


@router.get("/trades", response_model=list[TradeRead])
def list_trades(
    stock_id: int | None = None,
    trader_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[TradeRead]:
    return [
        TradeRead.model_validate(t)
        for t in order_service.list_trades(
            db, stock_id=stock_id, trader_id=trader_id, limit=limit
        )
    ]


@router.get("/market/{stock_id}/book", response_model=OrderBookRead)
def get_book(stock_id: int, db: Session = Depends(get_db)) -> OrderBookRead:
    if db.get(Stock, stock_id) is None:
        raise HTTPException(status_code=404, detail="stock not found")
    depth = books.get(stock_id).depth()
    return OrderBookRead(stock_id=stock_id, **depth)
