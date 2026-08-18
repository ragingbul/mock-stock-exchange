"use client";

import { useMemo } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PricePoint } from "@/hooks/usePriceChart";
import { fmtPct, num, signClass } from "@/lib/marketFormat";
import type { SidebarStock } from "./StockSidebar";

const UP = "#22c55e";
const DOWN = "#ef4444";

type Props = {
  stock: SidebarStock | null;
  priceSeries: PricePoint[];
  chartLoading?: boolean;
  qty: number;
  onQtyChange: (n: number) => void;
  holdingQty: number;
  tradingEnabled: boolean;
  onBuy: () => void;
  onSell: () => void;
  confirmSide: "buy" | "sell" | null;
  confirmLoading: boolean;
  confirmError: string | null;
  onConfirm: () => void;
  onCancelConfirm: () => void;
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
  chartLoading = false,
  qty,
  onQtyChange,
  holdingQty,
  tradingEnabled,
  onBuy,
  onSell,
  confirmSide,
  confirmLoading,
  confirmError,
  onConfirm,
  onCancelConfirm,
  ipo,
  ipoLots,
  onIpoLotsChange,
  onIpoApply,
}: Props) {
  const chartStroke =
    priceSeries.length >= 2 && priceSeries[priceSeries.length - 1].px >= priceSeries[0].px ? UP : DOWN;

  const yDomain = useMemo((): [number, number] => {
    if (priceSeries.length === 0) return [0, 1];
    const prices = priceSeries.map((p) => p.px);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const pad = Math.max((max - min) * 0.02, max * 0.005, 0.05);
    return [min - pad, max + pad];
  }, [priceSeries]);

  const estimatedValue = stock ? qty * num(stock.last_traded_price) : 0;
  const canTrade = tradingEnabled && !!stock;
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

      <div className="relative mt-4 h-72 border border-white/10 p-2 lg:h-96">
        {chartLoading && priceSeries.length === 0 && (
          <p className="absolute inset-0 flex items-center justify-center text-xs text-white/30">Loading chart…</p>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={priceSeries}>
            <XAxis dataKey="t" hide />
            <YAxis domain={yDomain} width={48} tick={{ fill: "#888", fontSize: 10 }} />
            <Tooltip contentStyle={{ background: "#000", border: "1px solid #333", fontSize: 11 }} />
            <Line
              type="monotone"
              dataKey="px"
              stroke={chartStroke}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {!tradingEnabled && (
        <p className="mt-3 border border-yellow-700/40 bg-yellow-900/20 px-3 py-2 text-xs text-yellow-300">
          Trading opens when admin starts the simulation.
        </p>
      )}

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
          disabled={!canTrade}
          title={!tradingEnabled ? "Wait for admin to start simulation" : undefined}
          className="bg-[#22c55e] py-3 text-black disabled:opacity-40"
          onClick={onBuy}
        >
          BUY
        </button>
        <button
          type="button"
          disabled={!canTrade}
          title={!tradingEnabled ? "Wait for admin to start simulation" : undefined}
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

      {confirmSide && stock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4">
          <div className="w-full max-w-sm border border-white/25 bg-black p-4">
            <p className="text-xs text-white/40">Confirm order</p>
            <p className="mt-2 text-lg">
              {confirmSide === "buy" ? "Buy" : "Sell"} {qty} × {stock.ticker}
            </p>
            <p className="mt-1 text-sm text-white/50">
              Est. value ₹{estimatedValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </p>
            {confirmError && <p className="mt-2 text-xs text-[#ef4444]">{confirmError}</p>}
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                className="flex-1 border border-white/25 py-2"
                disabled={confirmLoading}
                onClick={onCancelConfirm}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`flex-1 py-2 text-black ${confirmSide === "buy" ? "bg-[#22c55e]" : "bg-[#ef4444]"}`}
                disabled={confirmLoading}
                onClick={onConfirm}
              >
                {confirmLoading ? "Submitting…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
