"""Order and market-data routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.exchange.book_registry import books
from app.realtime.ws_manager import manager
from app.schemas.orders import OrderBookRead, OrderCreate, OrderRead, TradeRead
from app.services import order_service
from app.services.order_service import OrderGatewayError

router = APIRouter(tags=["orders"])


@router.post("/orders", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> dict:
    try:
        order, trades = order_service.submit_order(
            db,
            trader_id=payload.trader_id,
            stock_id=payload.stock_id,
            side=payload.side,
            order_type=payload.order_type,
            quantity=payload.quantity,
            price=payload.price,
            client_order_id=payload.client_order_id,
        )
    except OrderGatewayError as exc:
        if exc.rejected_order is not None:
            return {
                "order": OrderRead.model_validate(exc.rejected_order).model_dump(mode="json"),
                "trades": [],
                "rejected": True,
                "detail": str(exc),
            }
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trade_payload = [TradeRead.model_validate(t).model_dump(mode="json") for t in trades]
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
    return {
        "order": OrderRead.model_validate(order).model_dump(mode="json"),
        "trades": trade_payload,
        "rejected": False,
    }


@router.delete("/orders/{order_id}", response_model=OrderRead)
async def cancel_order(
    order_id: int, trader_id: int | None = None, db: Session = Depends(get_db)
) -> OrderRead:
    try:
        order = order_service.cancel_order(db, order_id, trader_id=trader_id)
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
) -> list[OrderRead]:
    return [
        OrderRead.model_validate(o)
        for o in order_service.list_orders(
            db, trader_id=trader_id, stock_id=stock_id, open_only=open_only
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
def get_book(stock_id: int) -> OrderBookRead:
    depth = books.get(stock_id).depth()
    return OrderBookRead(stock_id=stock_id, **depth)
