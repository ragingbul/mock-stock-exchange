"""IPO admin + participant routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_trader
from app.models import Trader
from app.realtime.ws_manager import manager
from app.schemas.orders import IPOApply, IPOCreate
from app.services import ipo_service
from app.services.ipo_service import IPOServiceError

router = APIRouter(tags=["ipos"])


def _ipo_dict(ipo) -> dict:
    return {
        "id": ipo.id,
        "company_name": ipo.company_name,
        "ticker": ipo.ticker,
        "sector_id": ipo.sector_id,
        "issue_price": str(ipo.issue_price),
        "lot_size": ipo.lot_size,
        "total_lots": ipo.total_lots,
        "winning_lots": ipo.winning_lots,
        "maximum_lots_per_user": ipo.maximum_lots_per_user,
        "application_start": ipo.application_start.isoformat() if ipo.application_start else None,
        "application_end": ipo.application_end.isoformat() if ipo.application_end else None,
        "listing_time": ipo.listing_time.isoformat() if ipo.listing_time else None,
        "status": ipo.status.value,
        "stock_id": ipo.stock_id,
        "description": ipo.description,
    }


def _app_dict(app) -> dict:
    return {
        "id": app.id,
        "ipo_id": app.ipo_id,
        "trader_id": app.trader_id,
        "requested_lots": app.requested_lots,
        "allocated_lots": app.allocated_lots,
        "amount_blocked": str(app.amount_blocked),
        "amount_used": str(app.amount_used),
        "status": app.status.value,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


@router.get("/ipos")
def list_ipos(db: Session = Depends(get_db)) -> list[dict]:
    return [_ipo_dict(i) for i in ipo_service.list_ipos(db)]


@router.get("/ipos/open")
def list_open_ipos(db: Session = Depends(get_db)) -> list[dict]:
    return [_ipo_dict(i) for i in ipo_service.list_ipos(db) if i.status.value == "open"]


@router.post("/ipos/{ipo_id}/apply")
async def apply_ipo(
    ipo_id: int,
    payload: IPOApply,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> dict:
    if payload.trader_id != trader.id:
        raise HTTPException(403, "trader_id does not match authenticated session")
    try:
        app = ipo_service.apply_ipo(
            db, ipo_id=ipo_id, trader_id=trader.id, requested_lots=payload.requested_lots
        )
    except IPOServiceError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = _app_dict(app)
    await manager.broadcast("IPO_APPLICATION_UPDATED", data)
    await manager.broadcast("WALLET_UPDATED", {"trader_id": trader.id})
    return data


@router.get("/traders/{trader_id}/ipo-applications")
def trader_ipo_apps(
    trader_id: int,
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> list[dict]:
    if trader_id != trader.id:
        raise HTTPException(403, "trader_id does not match authenticated session")
    return [_app_dict(a) for a in ipo_service.list_applications(db, trader_id=trader.id)]


@router.post("/admin/ipos")
def admin_create_ipo(payload: IPOCreate, db: Session = Depends(get_db)) -> dict:
    try:
        ipo = ipo_service.create_ipo(db, **payload.model_dump())
    except IPOServiceError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _ipo_dict(ipo)


@router.patch("/admin/ipos/{ipo_id}")
def admin_update_ipo(ipo_id: int, payload: IPOCreate, db: Session = Depends(get_db)) -> dict:
    try:
        ipo = ipo_service.update_ipo(db, ipo_id, **payload.model_dump(exclude_unset=True))
    except IPOServiceError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _ipo_dict(ipo)


@router.post("/admin/ipos/{ipo_id}/open")
def admin_open_ipo(ipo_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return _ipo_dict(ipo_service.open_ipo(db, ipo_id))
    except IPOServiceError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/admin/ipos/{ipo_id}/close")
def admin_close_ipo(ipo_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return _ipo_dict(ipo_service.close_applications(db, ipo_id))
    except IPOServiceError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/admin/ipos/{ipo_id}/allot")
async def admin_allot_ipo(ipo_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        result = ipo_service.allot_ipo(db, ipo_id)
    except IPOServiceError as e:
        raise HTTPException(400, str(e)) from e
    await manager.broadcast("IPO_ALLOTMENT", result)
    for row in result.get("allocations", []):
        await manager.broadcast("WALLET_UPDATED", {"trader_id": row["trader_id"]})
        await manager.broadcast("IPO_APPLICATION_UPDATED", row)
    return result


@router.post("/admin/ipos/{ipo_id}/list")
async def admin_list_ipo(ipo_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        result = ipo_service.list_ipo(db, ipo_id)
    except IPOServiceError as e:
        raise HTTPException(400, str(e)) from e
    await manager.broadcast("IPO_LISTED", result)
    await manager.broadcast("PRICE_UPDATED", {"stock_id": result["stock_id"]})
    return result


@router.get("/admin/ipos/{ipo_id}/applications")
def admin_ipo_apps(ipo_id: int, db: Session = Depends(get_db)) -> list[dict]:
    return [_app_dict(a) for a in ipo_service.list_applications(db, ipo_id=ipo_id)]
