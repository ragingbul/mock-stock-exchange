"""Order / trade / market schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.order_enums import OrderSide, OrderStatus, OrderType


class OrderCreate(BaseModel):
    trader_id: int
    stock_id: int
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(gt=0)
    price: Decimal | None = None
    client_order_id: str | None = None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trader_id: int
    stock_id: int
    side: OrderSide
    order_type: OrderType
    quantity: int
    remaining_quantity: int
    price: Decimal | None
    status: OrderStatus
    reject_reason: str | None = None
    created_at: datetime | None = None


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    buy_order_id: int
    sell_order_id: int
    buyer_id: int
    seller_id: int
    quantity: int
    price: Decimal
    executed_at: datetime | None = None


class OrderBookRead(BaseModel):
    stock_id: int
    best_bid: str | None
    best_ask: str | None
    spread: str | None
    bids: list[dict]
    asks: list[dict]


class NewsCreate(BaseModel):
    title: str
    description: str
    affected_tickers: str = ""
    affected_sectors: str = ""
    market_wide: bool = False
    direction: int = Field(ge=-1, le=1, default=0)
    impact: Decimal = Field(ge=0, le=1, default=Decimal("0.5"))
    confidence: Decimal = Field(ge=0, le=1, default=Decimal("1"))
    duration_minutes: int = 20
    decay_rate: Decimal = Decimal("0.05")
    fundamental_impact_pct: Decimal | None = None
    market_wide_impact_pct: Decimal | None = None
    sector_impacts: dict[str, float] | None = None
    stock_impacts: dict[str, float] | None = None
    scheduled_at: datetime | None = None
    status: str | None = None


class NewsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    affected_tickers: str
    affected_sectors: str
    market_wide: bool
    direction: int
    impact: Decimal
    confidence: Decimal
    duration_minutes: int
    decay_rate: Decimal
    fundamental_impact_pct: Decimal | None
    market_wide_impact_pct: Decimal | None = None
    sector_impacts_json: str | None = None
    stock_impacts_json: str | None = None
    sector_impacts: dict[str, float] | None = None
    status: str | None = None
    is_released: bool
    released_at: datetime | None = None
    scheduled_at: datetime | None = None
    effective_impact: Decimal | None = None


class SessionUpdate(BaseModel):
    status: str
    name: str | None = None
    notes: str | None = None


class HaltRequest(BaseModel):
    stock_id: int | None = None
    halted: bool = True
    market_wide: bool = False


class ConditionalCreate(BaseModel):
    trader_id: int
    stock_id: int
    condition_type: str  # stop_loss | take_profit
    quantity: int = Field(gt=0)
    trigger_price: Decimal = Field(gt=0)


class ConditionalUpdate(BaseModel):
    quantity: int | None = Field(default=None, gt=0)
    trigger_price: Decimal | None = Field(default=None, gt=0)


class IPOCreate(BaseModel):
    company_name: str
    ticker: str
    sector_id: int | None = None
    issue_price: Decimal = Field(gt=0)
    lot_size: int = Field(gt=0)
    total_lots: int = Field(gt=0)
    winning_lots: int = Field(gt=0)
    maximum_lots_per_user: int = Field(default=2, gt=0)
    application_start: datetime | None = None
    application_end: datetime | None = None
    listing_time: datetime | None = None
    description: str | None = None
    status: str | None = "draft"


class IPOApply(BaseModel):
    trader_id: int
    requested_lots: int = Field(gt=0)


class SimulationSettingsUpdate(BaseModel):
    ai_tick_min_sec: float | None = None
    ai_tick_max_sec: float | None = None
    ai_scheduler_enabled: bool | None = None
    news_impact_tolerance_pct: float | None = None
    max_price_move_per_tick_pct: float | None = None
    max_daily_move_pct: float | None = None
    market_maker_aggressiveness: float | None = None
    ai_aggressiveness: float | None = None
    news_reaction_strength: float | None = None
    ipo_allocation_method: str | None = None
    max_ipo_lots_per_user: int | None = None
    news_combined_impact_cap_pct: float | None = None
