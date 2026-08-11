"""Sector catalogue and performance routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import SectorRead, StockRead
from app.api.routes.stocks import _to_stock_read
from app.services import sector_service
from app.services.sector_service import SectorServiceError

router = APIRouter(prefix="/sectors", tags=["sectors"])


@router.get("", response_model=list[SectorRead])
def list_sectors(db: Session = Depends(get_db)) -> list[SectorRead]:
    sector_service.ensure_sectors(db)
    out: list[SectorRead] = []
    for sector in sector_service.list_sectors(db):
        stocks = sector_service.list_stocks_in_sector(db, sector.id)
        out.append(
            SectorRead.model_validate(sector).model_copy(
                update={"stock_count": len(stocks)}
            )
        )
    return out


@router.get("/summary")
def all_sector_summaries(db: Session = Depends(get_db)) -> list[dict]:
    return sector_service.sector_summary(db)


@router.get("/{sector_id}", response_model=SectorRead)
def get_sector(sector_id: int, db: Session = Depends(get_db)) -> SectorRead:
    sector = sector_service.get_sector(db, sector_id)
    if sector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sector not found")
    stocks = sector_service.list_stocks_in_sector(db, sector.id)
    return SectorRead.model_validate(sector).model_copy(update={"stock_count": len(stocks)})


@router.get("/{sector_id}/stocks", response_model=list[StockRead])
def stocks_in_sector(sector_id: int, db: Session = Depends(get_db)) -> list[StockRead]:
    sector = sector_service.get_sector(db, sector_id)
    if sector is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sector not found")
    return [_to_stock_read(s) for s in sector_service.list_stocks_in_sector(db, sector_id)]


@router.get("/{sector_id}/summary")
def one_sector_summary(sector_id: int, db: Session = Depends(get_db)) -> dict:
    rows = sector_service.sector_summary(db, sector_id=sector_id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sector not found")
    return rows[0]
