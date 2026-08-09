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
    direction: int = Field(ge=-1, le=1)
    impact: Decimal = Field(ge=0, le=1)
    confidence: Decimal = Field(ge=0, le=1, default=Decimal("1"))
    duration_minutes: int = 20
    decay_rate: Decimal = Decimal("0.05")
    fundamental_impact_pct: Decimal | None = None


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
    is_released: bool
    released_at: datetime | None = None
    effective_impact: Decimal | None = None


class SessionUpdate(BaseModel):
    status: str
    name: str | None = None
    notes: str | None = None


class HaltRequest(BaseModel):
    stock_id: int | None = None
    halted: bool = True
    market_wide: bool = False
