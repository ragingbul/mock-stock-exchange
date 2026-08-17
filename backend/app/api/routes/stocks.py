"""Stock HTTP routes."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import require_admin
from app.schemas import StockCreate, StockRead
from app.seed.stocks import seed_default_stocks
from app.services import sector_service, stock_service
from app.services.stock_service import StockServiceError

router = APIRouter(prefix="/stocks", tags=["stocks"])
_bearer = HTTPBearer(auto_error=False)


def _require_stock_mutation_admin(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict | None:
    if not get_settings().is_production:
        return None
    return require_admin(request, credentials)


def _to_stock_read(stock) -> StockRead:  # type: ignore[no-untyped-def]
    previous = Decimal(stock.previous_close)
    last = Decimal(stock.last_traded_price)
    pct = (
        ((last - previous) / previous) * Decimal("100")
        if previous > 0
        else Decimal("0")
    )
    data = StockRead.model_validate(stock)
    sector = getattr(stock, "market_sector", None)
    return data.model_copy(
        update={
            "percent_change": pct.quantize(Decimal("0.0001")),
            "sector_id": stock.sector_id,
            "sector_slug": sector.slug if sector else None,
            "sector_name": sector.name if sector else None,
        }
    )


@router.post("", response_model=StockRead, status_code=status.HTTP_201_CREATED)
def create_stock(
    payload: StockCreate,
    db: Session = Depends(get_db),
    _auth: dict | None = Depends(_require_stock_mutation_admin),
) -> StockRead:
    try:
        stock = stock_service.create_stock(db, payload)
    except StockServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    stock = stock_service.get_stock(db, stock.id) or stock
    return _to_stock_read(stock)


@router.get("", response_model=list[StockRead])
def list_stocks(
    sector_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[StockRead]:
    return [_to_stock_read(s) for s in stock_service.list_stocks(db, sector_id=sector_id)]


@router.get("/{stock_id}", response_model=StockRead)
def get_stock(stock_id: int, db: Session = Depends(get_db)) -> StockRead:
    stock = stock_service.get_stock(db, stock_id)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
    return _to_stock_read(stock)


@router.post("/seed/defaults", status_code=status.HTTP_201_CREATED)
def seed_stocks(
    db: Session = Depends(get_db),
    _auth: dict | None = Depends(_require_stock_mutation_admin),
) -> dict:
    sector_service.ensure_sectors(db)
    created = seed_default_stocks(db)
    backfilled = sector_service.backfill_stock_sectors(db)
    return {"created": created, "universe_size": 10, "sectors_linked": backfilled}
