"use client";

import { useMemo, useState } from "react";
import { fmtMoney, fmtPct, signClass } from "@/lib/marketFormat";
import type { EnrichedHolding, PortfolioDetail, TransactionRow } from "@/lib/api";

type Props = {
  portfolio: PortfolioDetail | null;
  holdings: EnrichedHolding[];
  transactions: TransactionRow[];
  loading?: boolean;
};

type Tab = "holdings" | "summary" | "transactions";

export function WalletPanel({ portfolio, holdings, transactions, loading }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("holdings");

  const tabs: { id: Tab; label: string }[] = [
    { id: "holdings", label: "Holdings" },
    { id: "summary", label: "Summary" },
    { id: "transactions", label: "History" },
  ];

  return (
    <section className="border-t border-white/15 bg-black/95">
      <div className="flex flex-wrap gap-1 border-b border-white/10 px-3 py-2 sm:px-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1 text-[10px] uppercase tracking-wider ${
              activeTab === tab.id
                ? "border border-white/40 bg-white/10 text-white"
                : "border border-transparent text-white/40 hover:text-white/70"
            }`}
          >
            {tab.label}
          </button>
        ))}
        {loading && <span className="ml-auto text-[10px] text-white/30">Updating…</span>}
      </div>

      <div className="max-h-80 overflow-y-auto p-3 sm:p-4">
        {activeTab === "holdings" && <HoldingsTab holdings={holdings} />}
        {activeTab === "summary" && <SummaryTab portfolio={portfolio} />}
        {activeTab === "transactions" && <TransactionsTab rows={transactions} />}
      </div>
    </section>
  );
}

function HoldingsTab({ holdings }: { holdings: EnrichedHolding[] }) {
  if (!holdings.length) {
    return <p className="text-xs text-white/40">No holdings yet — buy stocks to build your portfolio.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-left text-[11px]">
        <thead>
          <tr className="text-white/40">
            <th className="pb-2 pr-3 font-normal">Ticker</th>
            <th className="pb-2 pr-3 font-normal">Qty</th>
            <th className="pb-2 pr-3 font-normal">Avg</th>
            <th className="pb-2 pr-3 font-normal">LTP</th>
            <th className="pb-2 pr-3 font-normal">Value</th>
            <th className="pb-2 pr-3 font-normal">P&L</th>
            <th className="pb-2 font-normal">Return</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.ticker ?? h.stock_id} className="border-t border-white/5">
              <td className="py-2 pr-3 font-medium">{h.ticker ?? "—"}</td>
              <td className="py-2 pr-3 tabular-nums">{h.quantity}</td>
              <td className="py-2 pr-3 tabular-nums">{fmtMoney(h.avg_cost)}</td>
              <td className="py-2 pr-3 tabular-nums">{fmtMoney(h.market_price)}</td>
              <td className="py-2 pr-3 tabular-nums">{fmtMoney(h.market_value)}</td>
              <td className={`py-2 pr-3 tabular-nums ${signClass(h.unrealized_pnl)}`}>
                {fmtMoney(h.unrealized_pnl)}
              </td>
              <td className={`py-2 tabular-nums ${signClass(h.return_pct)}`}>
                {h.return_pct != null ? fmtPct(h.return_pct) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SummaryTab({ portfolio }: { portfolio: PortfolioDetail | null }) {
  if (!portfolio) {
    return <p className="text-xs text-white/40">Loading portfolio…</p>;
  }

  const rows: [string, string][] = [
    ["Available cash", fmtMoney(portfolio.available_cash)],
    ["IPO blocked", fmtMoney(portfolio.cash_blocked_ipo)],
    ["Invested", fmtMoney(portfolio.invested)],
    ["Holdings value", fmtMoney(portfolio.holdings_value)],
    ["Portfolio value", fmtMoney(portfolio.portfolio_value)],
    ["Realized P&L", fmtMoney(portfolio.realized_pnl)],
    ["Unrealized P&L", fmtMoney(portfolio.unrealized_pnl)],
    ["Total P&L", fmtMoney(portfolio.total_pnl)],
    ["Return", fmtPct(portfolio.return_pct)],
    ["Starting capital", fmtMoney(portfolio.starting_capital)],
  ];

  return (
    <dl className="grid gap-2 text-xs sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-4 border border-white/10 px-3 py-2">
          <dt className="text-white/40">{label}</dt>
          <dd className="tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function TransactionsTab({ rows }: { rows: TransactionRow[] }) {
  const sorted = useMemo(
    () => [...rows].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()),
    [rows],
  );

  if (!sorted.length) {
    return <p className="text-xs text-white/40">No transactions yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-left text-[11px]">
        <thead>
          <tr className="text-white/40">
            <th className="pb-2 pr-3 font-normal">Time</th>
            <th className="pb-2 pr-3 font-normal">Ticker</th>
            <th className="pb-2 pr-3 font-normal">Side</th>
            <th className="pb-2 pr-3 font-normal">Qty</th>
            <th className="pb-2 pr-3 font-normal">Price</th>
            <th className="pb-2 font-normal">Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.id} className="border-t border-white/5">
              <td className="py-2 pr-3 text-white/50">
                {new Date(row.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </td>
              <td className="py-2 pr-3">{row.ticker ?? "—"}</td>
              <td
                className={`py-2 pr-3 uppercase ${
                  row.side === "buy" ? "text-[#22c55e]" : row.side === "sell" ? "text-[#ef4444]" : "text-white/60"
                }`}
              >
                {row.side ?? "—"}
              </td>
              <td className="py-2 pr-3 tabular-nums">{row.quantity}</td>
              <td className="py-2 pr-3 tabular-nums">{row.price != null ? fmtMoney(row.price) : "—"}</td>
              <td className="py-2 capitalize text-white/60">{row.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
