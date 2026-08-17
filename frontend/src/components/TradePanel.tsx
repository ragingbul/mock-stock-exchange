"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtPct, num, signClass } from "@/lib/marketFormat";
import type { SidebarStock } from "./StockSidebar";

const UP = "#22c55e";
const DOWN = "#ef4444";

type Props = {
  stock: SidebarStock | null;
  priceSeries: Array<{ t: string; px: number }>;
  qty: number;
  onQtyChange: (n: number) => void;
  holdingQty: number;
  onBuy: () => void;
  onSell: () => void;
  submitting: boolean;
  ipo?: {
    id: number;
    company_name: string;
    ticker: string;
    issue_price: string;
    lot_size: number;
    maximum_lots_per_user: number;
  } | null;
  ipoLots: number;
  onIpoLotsChange: (n: number) => void;
  onIpoApply?: () => void;
};

export function TradePanel({
  stock,
  priceSeries,
  qty,
  onQtyChange,
  holdingQty,
  onBuy,
  onSell,
  submitting,
  ipo,
  ipoLots,
  onIpoLotsChange,
  onIpoApply,
}: Props) {
  const chartStroke =
    priceSeries.length >= 2 && priceSeries[priceSeries.length - 1].px >= priceSeries[0].px ? UP : DOWN;
  const inputCls = "w-full border border-white/25 bg-black px-2 py-2 text-white outline-none focus:border-white";

  return (
    <main className="flex flex-col border border-white/15 bg-black p-4">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl">{stock?.company_name ?? "Select a stock"}</h1>
          <p className="text-xs text-white/50">{stock?.ticker ?? "—"}</p>
        </div>
        <div className="text-right">
          <p className="text-3xl tabular-nums">{stock ? num(stock.last_traded_price).toFixed(2) : "—"}</p>
          <p className={`text-sm ${signClass(stock?.percent_change)}`}>
            {stock ? fmtPct(stock.percent_change) : "—"}
          </p>
        </div>
      </div>

      <div className="mt-4 h-44 border border-white/10 p-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={priceSeries}>
            <XAxis dataKey="t" hide />
            <YAxis domain={["auto", "auto"]} width={48} tick={{ fill: "#888", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#000", border: "1px solid #333", fontSize: 11 }} />
            <Line type="monotone" dataKey="px" stroke={chartStroke} strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 max-w-xs">
        <label className="text-[10px] text-white/40">Quantity</label>
        <input
          type="number"
          min={1}
          className={`${inputCls} mt-1`}
          value={qty}
          onChange={(e) => onQtyChange(Number(e.target.value))}
        />
        <p className="mt-1 text-[10px] text-white/40">Holding: {holdingQty}</p>
      </div>

      <div className="mt-4 grid max-w-md grid-cols-2 gap-2">
        <button
          type="button"
          disabled={submitting || !stock}
          className="bg-[#22c55e] py-3 text-black disabled:opacity-40"
          onClick={onBuy}
        >
          BUY
        </button>
        <button
          type="button"
          disabled={submitting || !stock}
          className="bg-[#ef4444] py-3 text-black disabled:opacity-40"
          onClick={onSell}
        >
          SELL
        </button>
      </div>

      {ipo && onIpoApply && (
        <div className="mt-4 border border-white/15 p-3 text-xs">
          <p className="text-[#22c55e]">NEW IPO</p>
          <p className="mt-1">
            {ipo.company_name} ({ipo.ticker}) · ₹{ipo.issue_price} · lot {ipo.lot_size}
          </p>
          <div className="mt-2 flex gap-2">
            <input
              type="number"
              min={1}
              max={ipo.maximum_lots_per_user}
              className={inputCls}
              value={ipoLots}
              onChange={(e) => onIpoLotsChange(Number(e.target.value))}
            />
            <button type="button" className="border border-white/30 px-4" onClick={onIpoApply}>
              APPLY
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
