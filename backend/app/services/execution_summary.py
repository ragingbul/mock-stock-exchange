"""Human-readable execution results for participant UI."""

from __future__ import annotations

from decimal import Decimal

from app.models import Order, OrderSide, OrderStatus, Stock, Trade


_HUMAN_REASONS: dict[str, str] = {
    "no liquidity": "No one is offering to trade at the moment. Wait a moment and try again.",
    "insufficient cash": "You do not have enough cash for this purchase.",
    "insufficient holdings (short selling disabled)": "You do not own enough shares to sell.",
    "stock is closed or halted": "This stock is not trading right now.",
    "market is paused": "The market is paused. Trading will resume shortly.",
    "market is closed": "The market is closed.",
    "price outside circuit limits": "Price is too far from the allowed range.",
    "quantity must be positive": "Quantity must be greater than zero.",
}


def human_reason(raw: str) -> str:
    if raw in _HUMAN_REASONS:
        return _HUMAN_REASONS[raw]
    if raw.startswith("market is "):
        return f"The market is {raw.replace('market is ', '')}. Try again later."
    return raw


def build_execution_summary(
    order: Order,
    trades: list[Trade],
    stock: Stock | None,
) -> dict:
    ticker = stock.ticker if stock else "?"
    side = order.side.value
    side_word = "Bought" if order.side == OrderSide.BUY else "Sold"
    filled_qty = sum(t.quantity for t in trades)

    if order.status == OrderStatus.REJECTED:
        reason = human_reason(order.reject_reason or "order rejected")
        return {
            "status": "rejected",
            "executed": False,
            "filled_quantity": 0,
            "average_price": None,
            "total_notional": None,
            "ticker": ticker,
            "side": side,
            "message": reason,
        }

    if filled_qty == 0:
        reason = human_reason(order.reject_reason or "no liquidity")
        return {
            "status": "cancelled",
            "executed": False,
            "filled_quantity": 0,
            "average_price": None,
            "total_notional": None,
            "ticker": ticker,
            "side": side,
            "message": reason,
        }

    total = sum(Decimal(t.price) * t.quantity for t in trades)
    avg = (total / filled_qty).quantize(Decimal("0.0001"))
    total_str = str(total.quantize(Decimal("0.01")))

    if order.status == OrderStatus.PARTIALLY_FILLED:
        message = (
            f"PARTIAL FILL\n{side_word} {filled_qty} of {order.quantity} {ticker}\n"
            f"Average price: ₹{avg}\nTotal: ₹{total_str}"
        )
        status = "partial"
    else:
        message = (
            f"ORDER EXECUTED\n{side_word} {filled_qty} {ticker}\n"
            f"Average execution price: ₹{avg}\nTotal: ₹{total_str}"
        )
        status = "filled"

    return {
        "status": status,
        "executed": True,
        "filled_quantity": filled_qty,
        "average_price": str(avg),
        "total_notional": total_str,
        "ticker": ticker,
        "side": side,
        "message": message,
    }
