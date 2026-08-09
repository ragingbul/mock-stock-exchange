"""Public news + leaderboard routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.orders import NewsRead
from app.services import leaderboard_service, news_service
from app.services.news_service import effective_impact

router = APIRouter(tags=["market"])


@router.get("/news", response_model=list[NewsRead])
def public_news(db: Session = Depends(get_db)) -> list[NewsRead]:
    out = []
    for event in news_service.list_news(db, released_only=True):
        read = NewsRead.model_validate(event)
        out.append(read.model_copy(update={"effective_impact": effective_impact(event)}))
    return out


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
