"""Admin / exchange control routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import runner as ai_runner
from app.core.config import get_settings
from app.core.database import get_db
from app.models import AIAgent, MarketSession, Stock
from app.models.enums import MarketSessionStatus, TraderType
from app.models.order_enums import OrderStatus
from app.models import Order, Trade, Trader
from app.realtime.ws_manager import manager
from app.schemas.orders import HaltRequest, NewsCreate, NewsRead, SessionUpdate
from app.schemas import SectorAssign
from app.services import news_service, order_service, sector_service, stock_service
from app.services.liquidity_service import seed_all_liquidity
from app.services.news_service import effective_impact
from app.services.sector_service import SectorServiceError
from app.api.routes.stocks import _to_stock_read

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/simulation/start")
async def simulation_start(db: Session = Depends(get_db)) -> dict:
    from app.services.simulation_controller import SimulationControlError, start_simulation

    try:
        result = start_simulation(db)
    except SimulationControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await manager.broadcast("SIMULATION_STATUS", result)
    return result


@router.post("/simulation/stop")
async def simulation_stop(db: Session = Depends(get_db)) -> dict:
    from app.services.simulation_controller import SimulationControlError, stop_simulation

    try:
        result = stop_simulation(db)
    except SimulationControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await manager.broadcast("SIMULATION_STATUS", result)
    return result


@router.post("/simulation/reset")
async def simulation_reset(db: Session = Depends(get_db)) -> dict:
    from app.services.simulation_controller import SimulationControlError, reset_simulation

    try:
        result = reset_simulation(db)
    except SimulationControlError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    await manager.broadcast("SIMULATION_STATUS", result)
    return result


@router.get("/simulation/status")
def simulation_status(
    db: Session = Depends(get_db),
    include_checkpoints: bool = True,
) -> dict:
    from app.services.simulation_clock import status_dict
    from app.services.timeline_service import progress_snapshot

    state = status_dict(db)
    progress = progress_snapshot(db, state["elapsed_sec"], include_checkpoints=include_checkpoints)
    return {**state, **progress}


@router.get("/timeline/progress")
def timeline_progress(db: Session = Depends(get_db)) -> dict:
    from app.services.simulation_clock import get_or_create_state
    from app.services.timeline_service import progress_snapshot

    state = get_or_create_state(db)
    return progress_snapshot(db, float(state.sim_elapsed_sec))


def _market_status(db: Session) -> dict:
    session = db.scalar(select(MarketSession).order_by(MarketSession.id.desc()).limit(1))
    stocks = stock_service.list_stocks(db)
    halted = sum(1 for s in stocks if s.is_halted)
    ai_count = db.scalar(select(func.count(AIAgent.id))) or 0
    ai_enabled = db.scalar(
        select(func.count(AIAgent.id)).where(AIAgent.is_enabled.is_(True))
    ) or 0
    status = session.status.value if session else "none"
    online = (
        session is not None
        and session.status == MarketSessionStatus.OPEN
        and halted < len(stocks)
    )
    return {
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "session_id": session.id if session else None,
        "session_status": status,
        "market_online": online,
        "stocks_total": len(stocks),
        "stocks_halted": halted,
        "ai_agents": int(ai_count),
        "ai_agents_enabled": int(ai_enabled),
    }


@router.post("/session/start")
async def start_session(name: str = "Live Session", db: Session = Depends(get_db)) -> dict:
    session = MarketSession(
        name=name,
        status=MarketSessionStatus.OPEN,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    await manager.broadcast("MARKET_HALTED", {"halted": False, "status": "open"})
    return {"id": session.id, "status": session.status.value}


@router.post("/session/pause")
async def pause_session(db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import select

    session = db.scalar(select(MarketSession).order_by(MarketSession.id.desc()).limit(1))
    if not session:
        raise HTTPException(404, "no session")
    session.status = MarketSessionStatus.PAUSED
    db.commit()
    await manager.broadcast("MARKET_HALTED", {"halted": True, "status": "paused"})
    return {"id": session.id, "status": session.status.value}


@router.post("/session/resume")
async def resume_session(db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import select

    session = db.scalar(select(MarketSession).order_by(MarketSession.id.desc()).limit(1))
    if not session:
        raise HTTPException(404, "no session")
    session.status = MarketSessionStatus.OPEN
    db.commit()
    await manager.broadcast("MARKET_HALTED", {"halted": False, "status": "open"})
    return {"id": session.id, "status": session.status.value}


@router.post("/halt")
async def halt(payload: HaltRequest, db: Session = Depends(get_db)) -> dict:
    if payload.market_wide:
        for stock in stock_service.list_stocks(db):
            stock.is_halted = payload.halted
        db.commit()
    elif payload.stock_id is not None:
        stock = db.get(Stock, payload.stock_id)
        if not stock:
            raise HTTPException(404, "stock not found")
        stock.is_halted = payload.halted
        db.commit()
    else:
        raise HTTPException(400, "stock_id or market_wide required")
    await manager.broadcast("MARKET_HALTED", payload.model_dump())
    return {"ok": True}


@router.post("/news", response_model=NewsRead)
def create_news(payload: NewsCreate, db: Session = Depends(get_db)) -> NewsRead:
    data = payload.model_dump()
    event = news_service.create_news(db, **data)
    return NewsRead.model_validate(event)


@router.post("/news/{event_id}/release", response_model=NewsRead)
async def release_news(event_id: int, db: Session = Depends(get_db)) -> NewsRead:
    try:
        event = news_service.release_news(db, event_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    detail = news_service.news_detail_dict(event)
    read = NewsRead.model_validate(event)
    read = read.model_copy(update={"effective_impact": effective_impact(event)})
    await manager.broadcast("NEWS_RELEASED", detail)
    return read


@router.post("/news/{event_id}/cancel")
def cancel_news(event_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        event = news_service.cancel_news(db, event_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"id": event.id, "status": event.status}


@router.get("/news", response_model=list[NewsRead])
def list_news(db: Session = Depends(get_db)) -> list[NewsRead]:
    out = []
    for event in news_service.list_news(db, include_scheduled=True):
        read = NewsRead.model_validate(event)
        out.append(read.model_copy(update={"effective_impact": effective_impact(event)}))
    return out


@router.get("/simulation-settings")
def get_sim_settings(db: Session = Depends(get_db)) -> dict:
    from app.services.simulation_settings_service import get_or_create_settings, settings_dict

    return settings_dict(get_or_create_settings(db))


@router.patch("/simulation-settings")
def patch_sim_settings(payload: dict, db: Session = Depends(get_db)) -> dict:
    from app.services.simulation_settings_service import settings_dict, update_settings
    from app.schemas.orders import SimulationSettingsUpdate

    parsed = SimulationSettingsUpdate.model_validate(payload)
    row = update_settings(db, **parsed.model_dump(exclude_unset=True))
    return settings_dict(row)


@router.post("/ai/scheduler/start")
def start_ai_scheduler(db: Session = Depends(get_db)) -> dict:
    from app.services import ai_scheduler
    from app.services.simulation_settings_service import update_settings

    update_settings(db, ai_scheduler_enabled=True)
    ai_scheduler.start_scheduler()
    return {"ok": True, **ai_scheduler.scheduler_status()}


@router.post("/ai/scheduler/stop")
def stop_ai_scheduler(db: Session = Depends(get_db)) -> dict:
    from app.services import ai_scheduler
    from app.services.simulation_settings_service import update_settings

    update_settings(db, ai_scheduler_enabled=False)
    ai_scheduler.stop_scheduler()
    return {"ok": True, **ai_scheduler.scheduler_status()}


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    trade_count = db.scalar(select(func.count(Trade.id))) or 0
    open_count = db.scalar(
        select(func.count(Order.id)).where(
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
        )
    ) or 0
    stock_count = len(stock_service.list_stocks(db))
    human_count = db.scalar(
        select(func.count(Trader.id)).where(Trader.trader_type == TraderType.HUMAN)
    ) or 0

    return {
        "stocks": stock_count,
        "trades": int(trade_count),
        "open_orders": int(open_count),
        "human_traders": int(human_count),
        "starting_capital": settings.default_starting_capital,
        "circuit_pct": settings.default_circuit_pct,
        **_market_status(db),
    }


@router.get("/market-status")
def market_status(db: Session = Depends(get_db)) -> dict:
    return _market_status(db)


@router.post("/ai/seed")
def seed_ai(db: Session = Depends(get_db)) -> dict:
    created = ai_runner.seed_default_agents(db)
    synced = ai_runner.sync_intensity_configs(db)
    return {"created": created, "configs_synced": synced}


@router.post("/ai/tick")
def ai_tick(db: Session = Depends(get_db)) -> dict:
    results = ai_runner.run_all_agents(db)
    return {"actions": len(results), "results": results[:50]}


@router.post("/bootstrap")
def bootstrap(db: Session = Depends(get_db)) -> dict:
    from app.services.simulation_controller import bootstrap_universe

    session = MarketSession(
        name="Bootstrapped Session",
        status=MarketSessionStatus.OPEN,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.flush()

    result = bootstrap_universe(db)
    db.refresh(session)
    return {
        **result,
        "session_id": session.id,
    }


@router.patch("/stocks/{stock_id}/sector")
def admin_assign_sector(
    stock_id: int,
    payload: SectorAssign,
    db: Session = Depends(get_db),
) -> dict:
    try:
        stock = sector_service.assign_stock_sector(
            db,
            stock_id,
            sector_id=payload.sector_id,
            sector_slug=payload.sector_slug,
        )
    except SectorServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    stock = stock_service.get_stock(db, stock.id) or stock
    return {"stock": _to_stock_read(stock).model_dump(mode="json")}


@router.post("/sectors/seed")
def admin_seed_sectors(db: Session = Depends(get_db)) -> dict:
    created = sector_service.seed_default_sectors(db)
    linked = sector_service.backfill_stock_sectors(db)
    return {"sectors_created": created, "stocks_linked": linked}
