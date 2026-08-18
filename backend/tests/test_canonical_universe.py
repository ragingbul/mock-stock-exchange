"""Canonical TRADEVERSE stock universe validation."""

from app.seed.tradeverse_stocks import (
    canonical_tradable_count,
    canonical_tradable_tickers,
    canonical_total_count,
)
from app.services import sector_service, simulation_controller, stock_service


def test_canonical_universe_after_reset(client):
    res = client.post("/api/v1/admin/simulation/reset")
    assert res.status_code == 200
    body = res.json()
    assert body["message"] == "Canonical stock universe loaded successfully"
    assert body["tradable_stocks"] == canonical_tradable_count()
    assert body["expected_tradable"] == canonical_tradable_count()

    stocks = client.get("/api/v1/stocks").json()
    tickers = {s["ticker"] for s in stocks}
    assert len(tickers) == len(stocks), "duplicate tickers in stock list"
    assert tickers == set(canonical_tradable_tickers())

    sectors = client.get("/api/v1/market/sectors").json()
    sector_stock_ids = {row["stock_id"] for sec in sectors for row in sec["stocks"]}
    open_ids = {s["id"] for s in stocks if s.get("is_open", True)}
    assert sector_stock_ids.issubset(open_ids)


def test_canonical_counts_from_source():
    assert canonical_tradable_count() == len(canonical_tradable_tickers())
    assert canonical_total_count() == canonical_tradable_count() + 5


def test_all_tradable_stocks_have_sectors(db_session):
    simulation_controller.bootstrap_universe(db_session)
    for stock in stock_service.list_stocks(db_session):
        assert stock.sector_id is not None, f"{stock.ticker} missing sector_id"
        sector = sector_service.get_sector(db_session, stock.sector_id)
        assert sector is not None
