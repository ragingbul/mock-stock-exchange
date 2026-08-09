"""Exchange core: order book, matching, settlement.

Matching engine must stay independent of AI, news, UI, and sentiment.
"""

from app.exchange.book_registry import books
from app.exchange.matching_engine import MatchingEngine
from app.exchange.order_book import OrderBook

__all__ = ["OrderBook", "MatchingEngine", "books"]
