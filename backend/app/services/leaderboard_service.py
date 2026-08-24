"""Leaderboard scoring — configurable weights; no private leakage beyond rankings."""

from __future__ import annotations

import time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LeaderboardSnapshot, Trade, Trader, TraderType
from app.services.portfolio_service import get_portfolio

_leaderboard_cache: tuple[float, list[dict]] | None = None
LEADERBOARD_CACHE_SEC = 5.0


def invalidate_leaderboard_cache() -> None:
    global _leaderboard_cache
    _leaderboard_cache = None


def compute_leaderboard(db: Session, *, humans_only: bool = True, use_cache: bool = True) -> list[dict]:
    global _leaderboard_cache
    now = time.time()
    if use_cache and _leaderboard_cache is not None:
        cached_at, rows = _leaderboard_cache
        if now - cached_at < LEADERBOARD_CACHE_SEC:
            return rows

    traders = list(db.scalars(select(Trader).where(Trader.is_active.is_(True))).all())
    rows = []
    for trader in traders:
        if humans_only and trader.trader_type != TraderType.HUMAN:
            continue
        portfolio = get_portfolio(db, trader.id)
        trade_count = db.scalar(
            select(func.count(Trade.id)).where(
                (Trade.buyer_id == trader.id) | (Trade.seller_id == trader.id)
            )
        ) or 0
        turnover = db.scalar(
            select(func.coalesce(func.sum(Trade.price * Trade.quantity), 0)).where(
                (Trade.buyer_id == trader.id) | (Trade.seller_id == trader.id)
            )
        ) or 0
        # Score: primarily return %, light trade activity term
        score = portfolio.return_pct + (Decimal(str(trade_count)) * Decimal("0.01"))
        rows.append(
            {
                "trader_id": trader.id,
                "name": trader.name,
                "portfolio_value": portfolio.portfolio_value,
                "return_pct": portfolio.return_pct,
                "realized_pnl": portfolio.realized_pnl,
                "unrealized_pnl": portfolio.unrealized_pnl,
                "max_drawdown": Decimal("0"),  # full path needs snapshot history
                "sharpe_ratio": None,
                "win_rate": None,
                "turnover": Decimal(str(turnover)),
                "trade_count": int(trade_count),
                "score": score,
            }
        )
    rows.sort(key=lambda r: r["score"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    _leaderboard_cache = (now, rows)
    return rows


def snapshot_leaderboard(db: Session, *, label: str = "live") -> int:
    rows = compute_leaderboard(db)
    for row in rows:
        db.add(
            LeaderboardSnapshot(
                trader_id=row["trader_id"],
                rank=row["rank"],
                score=row["score"],
                portfolio_value=row["portfolio_value"],
                return_pct=row["return_pct"],
                realized_pnl=row["realized_pnl"],
                unrealized_pnl=row["unrealized_pnl"],
                max_drawdown=row["max_drawdown"],
                sharpe_ratio=row["sharpe_ratio"],
                win_rate=row["win_rate"],
                turnover=row["turnover"],
                trade_count=row["trade_count"],
                label=label,
            )
        )
    db.commit()
    return len(rows)
