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
    <section className="border-t border-white/15 bg-gradient-to-b from-white/[0.03] to-black">
      {portfolio && (
        <div className="grid grid-cols-2 gap-2 border-b border-white/10 px-3 py-3 sm:px-4">
          <div className="rounded border border-white/10 bg-white/[0.04] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-white/40">Portfolio</p>
            <p className="mt-1 text-lg font-semibold tabular-nums">{fmtMoney(portfolio.portfolio_value)}</p>
          </div>
          <div className="rounded border border-white/10 bg-white/[0.04] px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-white/40">Total P&L</p>
            <p className={`mt-1 text-lg font-semibold tabular-nums ${signClass(portfolio.total_pnl)}`}>
              {fmtMoney(portfolio.total_pnl)}
            </p>
            <p className={`text-[10px] tabular-nums ${signClass(portfolio.return_pct)}`}>
              {fmtPct(portfolio.return_pct)} return
            </p>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 border-b border-white/10 px-3 py-2 sm:px-4">
        <div className="inline-flex rounded-full border border-white/15 bg-black/60 p-0.5">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`rounded-full px-3 py-1 text-[10px] uppercase tracking-wider transition-colors ${
                activeTab === tab.id
                  ? "bg-white/15 text-white"
                  : "text-white/40 hover:text-white/70"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
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
    return (
      <p className="rounded border border-dashed border-white/15 px-4 py-8 text-center text-xs text-white/40">
        No holdings yet — buy stocks to build your portfolio.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {holdings.map((h) => (
        <div
          key={h.ticker ?? h.stock_id}
          className="rounded border border-white/10 bg-white/[0.03] px-3 py-2.5"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-bold tracking-wide">{h.ticker ?? "—"}</p>
              <p className="mt-1 text-[10px] text-white/40">{h.quantity} shares</p>
            </div>
            <div className="text-right">
              <p className={`text-sm font-semibold tabular-nums ${signClass(h.unrealized_pnl)}`}>
                {fmtMoney(h.unrealized_pnl)}
              </p>
              <p className={`text-[10px] tabular-nums ${signClass(h.return_pct)}`}>
                {h.return_pct != null ? fmtPct(h.return_pct) : "—"}
              </p>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] text-white/50">
            <div>
              <p className="text-white/30">Avg</p>
              <p className="tabular-nums text-white/80">{fmtMoney(h.avg_cost)}</p>
            </div>
            <div>
              <p className="text-white/30">LTP</p>
              <p className="tabular-nums text-white/80">{fmtMoney(h.market_price)}</p>
            </div>
            <div>
              <p className="text-white/30">Value</p>
              <p className="tabular-nums text-white/80">{fmtMoney(h.market_value)}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SummaryTab({ portfolio }: { portfolio: PortfolioDetail | null }) {
  if (!portfolio) {
    return <p className="text-xs text-white/40">Loading portfolio…</p>;
  }

  const cashRows: [string, string][] = [
    ["Available cash", fmtMoney(portfolio.available_cash)],
    ["IPO blocked", fmtMoney(portfolio.cash_blocked_ipo)],
    ["Invested", fmtMoney(portfolio.invested)],
    ["Holdings value", fmtMoney(portfolio.holdings_value)],
    ["Starting capital", fmtMoney(portfolio.starting_capital)],
  ];

  const pnlRows: [string, string][] = [
    ["Realized P&L", fmtMoney(portfolio.realized_pnl)],
    ["Unrealized P&L", fmtMoney(portfolio.unrealized_pnl)],
    ["Total P&L", fmtMoney(portfolio.total_pnl)],
    ["Return", fmtPct(portfolio.return_pct)],
  ];

  return (
    <div className="space-y-3">
      <div>
        <p className="mb-2 text-[10px] uppercase tracking-wider text-white/40">Cash</p>
        <dl className="grid gap-2 sm:grid-cols-2">
          {cashRows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 rounded border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
              <dt className="text-white/40">{label}</dt>
              <dd className="tabular-nums text-white/90">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div>
        <p className="mb-2 text-[10px] uppercase tracking-wider text-white/40">Performance</p>
        <dl className="grid gap-2 sm:grid-cols-2">
          {pnlRows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 rounded border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
              <dt className="text-white/40">{label}</dt>
              <dd className={`tabular-nums ${label.includes("P&L") || label === "Return" ? signClass(value) : "text-white/90"}`}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

function TransactionsTab({ rows }: { rows: TransactionRow[] }) {
  const sorted = useMemo(
    () => [...rows].sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()),
    [rows],
  );

  if (!sorted.length) {
    return (
      <p className="rounded border border-dashed border-white/15 px-4 py-8 text-center text-xs text-white/40">
        No transactions yet.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {sorted.map((row, idx) => (
        <div
          key={row.id}
          className={`flex flex-wrap items-center gap-2 rounded px-2 py-2 text-[11px] ${
            idx % 2 === 0 ? "bg-white/[0.03]" : "bg-transparent"
          }`}
        >
          <span className="w-16 shrink-0 text-white/40">
            {new Date(row.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
          <span className="w-16 shrink-0 font-medium">{row.ticker ?? "—"}</span>
          {row.side && (
            <span
              className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                row.side === "buy"
                  ? "bg-[#22c55e]/20 text-[#22c55e]"
                  : "bg-[#ef4444]/20 text-[#ef4444]"
              }`}
            >
              {row.side}
            </span>
          )}
          <span className="tabular-nums text-white/70">{row.quantity} @ {row.price != null ? fmtMoney(row.price) : "—"}</span>
          <span className="ml-auto capitalize text-white/40">{row.status}</span>
        </div>
      ))}
    </div>
  );
}
