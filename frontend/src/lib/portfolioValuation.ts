import { num } from "@/lib/marketFormat";
import type { EnrichedHolding, HoldingDetail } from "@/lib/api";

export type WalletSnapshot = {
  available_cash: string;
  portfolio_value: string;
  total_pnl: string;
  return_pct: string;
  starting_capital?: string;
};

export type PortfolioSnapshot = {
  holdings: Array<{ ticker: string | null; quantity: number; avg_cost?: string }>;
  starting_capital?: string;
  realized_pnl?: string;
  cash_blocked_ipo?: string;
};

type PricedStock = { ticker: string; last_traded_price: string };

/** Recompute portfolio value and P&L from live LTPs without hitting the API. */
export function markWalletToMarket(
  wallet: WalletSnapshot | null,
  portfolio: PortfolioSnapshot | null,
  stocks: PricedStock[],
): WalletSnapshot | null {
  if (!wallet) return null;
  if (!portfolio) return wallet;

  const priceByTicker = new Map(stocks.map((s) => [s.ticker, num(s.last_traded_price)]));
  let holdingsValue = 0;
  let costBasis = 0;

  for (const h of portfolio.holdings) {
    if (!h.ticker || h.quantity <= 0) continue;
    const ltp = priceByTicker.get(h.ticker) ?? 0;
    const avg = num(h.avg_cost);
    holdingsValue += h.quantity * ltp;
    costBasis += h.quantity * avg;
  }

  const cash = num(wallet.available_cash);
  const blocked = num(portfolio.cash_blocked_ipo ?? "0");
  const starting = num(portfolio.starting_capital ?? wallet.starting_capital ?? "0");
  const realized = num(portfolio.realized_pnl ?? "0");
  const portfolioValue = cash + blocked + holdingsValue;
  const totalPnl = realized + (holdingsValue - costBasis);
  const returnPct = starting > 0 ? ((portfolioValue - starting) / starting) * 100 : 0;

  return {
    ...wallet,
    portfolio_value: portfolioValue.toFixed(2),
    total_pnl: totalPnl.toFixed(2),
    return_pct: returnPct.toFixed(4),
  };
}

/** Live mark-to-market per holding row for wallet panel. */
export function markHoldingsToMarket(
  holdings: HoldingDetail[],
  stocks: PricedStock[],
): EnrichedHolding[] {
  const priceByTicker = new Map(stocks.map((s) => [s.ticker, num(s.last_traded_price)]));

  return holdings
    .filter((h) => h.quantity > 0)
    .map((h) => {
      const ltp = h.ticker ? (priceByTicker.get(h.ticker) ?? num(h.market_price)) : num(h.market_price);
      const avg = num(h.avg_cost);
      const marketValue = h.quantity * ltp;
      const costBasis = h.quantity * avg;
      const unrealized = marketValue - costBasis;
      const returnPct = costBasis > 0 ? ((marketValue - costBasis) / costBasis) * 100 : 0;
      return {
        ...h,
        market_price: ltp.toFixed(2),
        market_value: marketValue.toFixed(2),
        unrealized_pnl: unrealized.toFixed(2),
        return_pct: returnPct.toFixed(4),
      };
    });
}
