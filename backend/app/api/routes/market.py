"""Public news + leaderboard + sector market views."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.orders import NewsRead
from app.services import leaderboard_service, news_service, sector_service
from app.services.news_service import effective_impact
from app.services.simulation_clock import status_dict

router = APIRouter(tags=["market"])


@router.get("/market/status")
def market_status(db: Session = Depends(get_db)) -> dict:
    """Public market dashboard data — no checkpoint spoilers."""
    clock = status_dict(db)
    change = sector_service.market_change_pct(db)
    events = news_service.list_news(db, released_only=True)
    latest = None
    if events:
        detail = news_service.news_detail_dict(events[0])
        latest = {
            "id": detail["id"],
            "title": detail["title"],
            "description": detail["description"],
            "brief_points": detail.get("brief_points") or [],
            "released_at": detail["released_at"],
            "sector_impacts": detail["sector_impacts"],
        }
    return {
        "elapsed": clock["elapsed"],
        "current_phase": clock["current_phase"],
        "status": clock["status"],
        "market_change_pct": str(change),
        "latest_news": latest,
    }


@router.get("/news", response_model=list[NewsRead])
def public_news(db: Session = Depends(get_db)) -> list[NewsRead]:
    out = []
    for event in news_service.list_news(db, released_only=True):
        detail = news_service.news_detail_dict(event)
        read = NewsRead.model_validate(event)
        out.append(
            read.model_copy(
                update={
                    "effective_impact": effective_impact(event),
                    "sector_impacts": detail["sector_impacts"],
                    "brief_points": detail.get("brief_points") or [],
                }
            )
        )
    return out


@router.get("/news/{news_id}")
def news_detail(news_id: int, db: Session = Depends(get_db)) -> dict:
    event = news_service.get_news(db, news_id)
    if event is None or not event.is_released:
        from fastapi import HTTPException

        raise HTTPException(404, "news not found")
    return news_service.news_detail_dict(event)


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)) -> list[dict]:
    # Public: rank, name, return%, portfolio value — no private order details
    rows = leaderboard_service.compute_leaderboard(db)
    return [
        {
            "rank": r["rank"],
            "trader_id": r["trader_id"],
            "name": r["name"],
            "portfolio_value": str(r["portfolio_value"]),
            "return_pct": str(r["return_pct"]),
            "trade_count": r["trade_count"],
        }
        for r in rows
    ]


@router.get("/market/sectors")
def market_sectors(db: Session = Depends(get_db)) -> list[dict]:
    """Stocks grouped by sector with performance summary."""
    return sector_service.sector_summary(db)
