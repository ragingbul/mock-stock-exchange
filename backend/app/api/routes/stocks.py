"""Stock HTTP routes."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import StockCreate, StockRead
from app.seed.stocks import seed_default_stocks
from app.services import stock_service
from app.services.stock_service import StockServiceError

router = APIRouter(prefix="/stocks", tags=["stocks"])


def _to_stock_read(stock) -> StockRead:  # type: ignore[no-untyped-def]
    previous = Decimal(stock.previous_close)
    last = Decimal(stock.last_traded_price)
    pct = (
        ((last - previous) / previous) * Decimal("100")
        if previous > 0
        else Decimal("0")
    )
    data = StockRead.model_validate(stock)
    return data.model_copy(update={"percent_change": pct.quantize(Decimal("0.0001"))})


@router.post("", response_model=StockRead, status_code=status.HTTP_201_CREATED)
def create_stock(payload: StockCreate, db: Session = Depends(get_db)) -> StockRead:
    try:
        stock = stock_service.create_stock(db, payload)
    except StockServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_stock_read(stock)


@router.get("", response_model=list[StockRead])
def list_stocks(db: Session = Depends(get_db)) -> list[StockRead]:
    return [_to_stock_read(s) for s in stock_service.list_stocks(db)]


@router.get("/{stock_id}", response_model=StockRead)
def get_stock(stock_id: int, db: Session = Depends(get_db)) -> StockRead:
    stock = stock_service.get_stock(db, stock_id)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
    return _to_stock_read(stock)


@router.post("/seed/defaults", status_code=status.HTTP_201_CREATED)
def seed_stocks(db: Session = Depends(get_db)) -> dict:
    created = seed_default_stocks(db)
    return {"created": created, "universe_size": 10}
