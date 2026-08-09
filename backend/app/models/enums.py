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


class Sector(str, Enum):
    TECH = "tech"
    AUTO = "auto"
    ENERGY = "energy"
    FINANCE = "finance"
    PHARMA = "pharma"
    RETAIL = "retail"
    INFRA = "infra"
    FOOD = "food"
    DATA = "data"
