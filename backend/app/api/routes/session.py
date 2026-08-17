"""Session bootstrap for terminal reconnect."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_trader
from app.models import NewsEvent, Trader
from app.services import ipo_service, leaderboard_service, portfolio_service, sector_service, stock_service
from app.services import news_service
from app.services.simulation_clock import status_dict

router = APIRouter(prefix="/session", tags=["session"])


def _percent_change(stock) -> str:
    previous = Decimal(stock.previous_close)
    last = Decimal(stock.last_traded_price)
    if previous <= 0:
        return "0.0000"
    pct = ((last - previous) / previous) * Decimal("100")
    return str(pct.quantize(Decimal("0.0001")))


def _ipo_dict(ipo) -> dict:
    return {
        "id": ipo.id,
        "company_name": ipo.company_name,
        "ticker": ipo.ticker,
        "issue_price": str(ipo.issue_price),
        "lot_size": ipo.lot_size,
        "maximum_lots_per_user": ipo.maximum_lots_per_user,
        "status": ipo.status.value,
    }


@router.get("/bootstrap")
def session_bootstrap(
    db: Session = Depends(get_db),
    trader: Trader = Depends(require_trader),
) -> dict:
    """Authoritative snapshot for terminal load / WS reconnect."""
    wallet = portfolio_service.get_wallet(db, trader.id).model_dump()
    portfolio = portfolio_service.get_portfolio(db, trader.id).model_dump()
    released_news = db.scalar(
        select(func.count(NewsEvent.id)).where(NewsEvent.is_released.is_(True))
    ) or 0
    news_rows = []
    for event in news_service.list_news(db, released_only=True)[:20]:
        detail = news_service.news_detail_dict(event)
        news_rows.append(
            {
                "id": detail["id"],
                "title": detail["title"],
                "description": detail.get("description"),
                "released_at": detail.get("released_at"),
            }
        )
    leaderboard_rows = [
        {
            "rank": r["rank"],
            "trader_id": r["trader_id"],
            "name": r["name"],
            "portfolio_value": str(r["portfolio_value"]),
            "return_pct": str(r["return_pct"]),
            "trade_count": int(r.get("trade_count") or 0),
        }
        for r in leaderboard_service.compute_leaderboard(db)[:15]
    ]
    open_ipos = [
        _ipo_dict(i) for i in ipo_service.list_ipos(db) if i.status.value == "open"
    ]
    ipo_apps = [
        {
            "id": a.id,
            "ipo_id": a.ipo_id,
            "requested_lots": a.requested_lots,
            "allocated_lots": a.allocated_lots,
            "status": a.status.value,
        }
        for a in ipo_service.list_applications(db, trader_id=trader.id)
    ]
    return {
        "simulation": status_dict(db),
        "wallet": wallet,
        "portfolio": portfolio,
        "stocks": [
            {
                "id": s.id,
                "ticker": s.ticker,
                "company_name": s.company_name,
                "ltp": str(s.last_traded_price),
                "last_traded_price": str(s.last_traded_price),
                "percent_change": _percent_change(s),
                "is_open": bool(s.is_open),
                "sector_slug": s.market_sector.slug if s.market_sector else None,
            }
            for s in stock_service.list_stocks(db)
        ],
        "sectors": sector_service.sector_summary(db),
        "released_news_count": int(released_news),
        "released_news": news_rows,
        "leaderboard": leaderboard_rows,
        "open_ipos": open_ipos,
        "ipo_applications": ipo_apps,
        "trader_id": trader.id,
    }
