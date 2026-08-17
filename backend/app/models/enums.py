"""Shared enums for core exchange entities."""

from enum import Enum


class UserRole(str, Enum):
    PARTICIPANT = "participant"
    ADMIN = "admin"


class TraderType(str, Enum):
    HUMAN = "human"
    AI = "ai"


class VolatilityClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class LiquidityClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FundamentalProfile(str, Enum):
    GROWTH = "growth"
    STABLE = "stable"
    DISTRESSED = "distressed"
    CYCLICAL = "cyclical"


class MarketSessionStatus(str, Enum):
    CREATED = "created"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class SimulationStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class StockStatus(str, Enum):
    ACTIVE = "active"
    DISSOLVED = "dissolved"


class TimelineEventType(str, Enum):
    NEWS = "NEWS"
    IPO_OPEN = "IPO_OPEN"
    IPO_CLOSE = "IPO_CLOSE"
    IPO_ALLOTMENT = "IPO_ALLOTMENT"
    IPO_LISTING = "IPO_LISTING"
    COMPANY_DISSOLUTION = "COMPANY_DISSOLUTION"
    SIMULATION_END = "SIMULATION_END"


class TimelineEventStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"


class Sector(str, Enum):
    """Legacy stock sector codes — mapped to MarketSector rows via slug."""

    TECH = "tech"
    AUTO = "auto"
    ENERGY = "energy"
    FINANCE = "finance"
    PHARMA = "pharma"
    RETAIL = "retail"
    INFRA = "infra"
    FOOD = "food"
    DATA = "data"
    # Spec aliases (optional; preferred path is MarketSector.slug)
    FINANCIALS = "financials"
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    CONSUMER = "consumer"
    INDUSTRIALS = "industrials"
    REAL_ESTATE = "real_estate"
    UTILITIES = "utilities"
    TELECOM = "telecom"
    AUTOMOTIVE = "automotive"
