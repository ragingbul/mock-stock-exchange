"""Pydantic schemas for users, traders, stocks, holdings, and portfolios."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    FundamentalProfile,
    LiquidityClass,
    MarketSessionStatus,
    Sector,
    TraderType,
    UserRole,
    VolatilityClass,
)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    role: UserRole = UserRole.PARTICIPANT
    password: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime | None = None


class TraderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    trader_type: TraderType = TraderType.HUMAN
    starting_capital: Decimal | None = None
    username: str | None = Field(
        default=None,
        description="Optional login username; creates a linked user when set.",
    )


class HoldingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    ticker: str | None = None
    quantity: int
    avg_cost: Decimal
    market_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None


class TraderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    trader_type: TraderType
    starting_capital: Decimal
    cash: Decimal
    realized_pnl: Decimal
    is_active: bool
    user_id: int | None = None
    created_at: datetime | None = None


class PortfolioRead(BaseModel):
    trader_id: int
    name: str
    cash: Decimal
    cash_blocked_ipo: Decimal = Decimal("0")
    available_cash: Decimal
    invested: Decimal
    starting_capital: Decimal
    holdings_value: Decimal
    portfolio_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    return_pct: Decimal
    holdings: list[HoldingRead]


class WalletRead(BaseModel):
    trader_id: int
    available_cash: Decimal
    cash_blocked_ipo: Decimal
    invested: Decimal
    portfolio_value: Decimal
    total_pnl: Decimal
    return_pct: Decimal
    starting_capital: Decimal


class StockCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    company_name: str
    sector: Sector
    sector_id: int | None = None
    starting_price: Decimal = Field(gt=0)
    shares_outstanding: int = Field(gt=0)
    fair_value: Decimal = Field(gt=0)
    volatility_class: VolatilityClass = VolatilityClass.MEDIUM
    liquidity_class: LiquidityClass = LiquidityClass.MEDIUM
    fundamental_profile: FundamentalProfile = FundamentalProfile.STABLE
    tick_size: Decimal | None = None
    description: str | None = None


class StockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    company_name: str
    sector: Sector
    sector_id: int | None = None
    sector_slug: str | None = None
    sector_name: str | None = None
    starting_price: Decimal
    last_traded_price: Decimal
    previous_close: Decimal
    shares_outstanding: int
    fair_value: Decimal
    volatility_class: VolatilityClass
    liquidity_class: LiquidityClass
    fundamental_profile: FundamentalProfile
    tick_size: Decimal
    is_open: bool
    is_halted: bool
    description: str | None = None
    percent_change: Decimal | None = None


class SectorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    display_order: int
    is_active: bool
    stock_count: int | None = None


class SectorAssign(BaseModel):
    sector_id: int | None = None
    sector_slug: str | None = None


class HoldingAdjust(BaseModel):
    """Admin/test helper to seed holdings before the matching engine exists."""

    stock_id: int
    quantity: int = Field(ge=0)
    avg_cost: Decimal = Field(ge=0)


class MarketSessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    notes: str | None = None


class MarketSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: MarketSessionStatus
    notes: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime | None = None
