"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet } from "@/lib/api";
import { num } from "@/lib/marketFormat";

export type PricePoint = { t: string; px: number };

const MAX_POINTS = 120;
const REFETCH_INTERVAL_MS = 30_000;

type TradeRow = { id: number; price: string; executed_at?: string };

function tradesToSeries(trades: TradeRow[]): PricePoint[] {
  const sorted = [...trades].sort((a, b) =>
    String(a.executed_at ?? a.id).localeCompare(String(b.executed_at ?? b.id)),
  );
  return sorted.map((tr) => ({
    t: tr.executed_at
      ? new Date(tr.executed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : `#${tr.id}`,
    px: num(tr.price),
  }));
}

function appendPoint(series: PricePoint[], px: number): PricePoint[] {
  const t = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const next = [...series, { t, px }];
  if (next.length > MAX_POINTS) return next.slice(next.length - MAX_POINTS);
  return next;
}

export type PriceUpdatePayload = {
  stock_id?: number;
  ltp?: string;
  trades?: Array<{ price: string }>;
};

export function usePriceChart(selectedId: number | null, fallbackPrice?: string) {
  const cacheRef = useRef<Map<number, PricePoint[]>>(new Map());
  const lastFetchRef = useRef<Map<number, number>>(new Map());
  const [priceSeries, setPriceSeries] = useState<PricePoint[]>([]);
  const [chartLoading, setChartLoading] = useState(false);

  const loadHistory = useCallback(
    async (stockId: number, force = false) => {
      const now = Date.now();
      const lastFetch = lastFetchRef.current.get(stockId) ?? 0;
      if (!force && now - lastFetch < REFETCH_INTERVAL_MS && cacheRef.current.has(stockId)) {
        setPriceSeries(cacheRef.current.get(stockId)!);
        return;
      }

      setChartLoading(true);
      try {
        const trades = await apiGet<TradeRow[]>(`/trades?stock_id=${stockId}&limit=${MAX_POINTS}`);
        let series: PricePoint[];
        if (trades.length > 0) {
          series = tradesToSeries(trades);
        } else if (fallbackPrice) {
          series = [{ t: "now", px: num(fallbackPrice) }];
        } else {
          series = cacheRef.current.get(stockId) ?? [];
        }
        cacheRef.current.set(stockId, series);
        lastFetchRef.current.set(stockId, now);
        setPriceSeries(series);
      } finally {
        setChartLoading(false);
      }
    },
    [fallbackPrice],
  );

  useEffect(() => {
    if (!selectedId) return;
    const cached = cacheRef.current.get(selectedId);
    if (cached?.length) {
      setPriceSeries(cached);
    }
    void loadHistory(selectedId);
  }, [selectedId, loadHistory]);

  const handlePriceUpdate = useCallback(
    (payload: PriceUpdatePayload) => {
      const stockId = payload.stock_id;
      if (!stockId) return;

      let px: number | null = null;
      if (payload.ltp) px = num(payload.ltp);
      else if (payload.trades?.length) px = num(payload.trades[payload.trades.length - 1].price);
      if (px === null) return;

      const cached = cacheRef.current.get(stockId) ?? [];
      const base = cached.length ? cached : [{ t: "now", px }];
      const updated = appendPoint(base, px);
      cacheRef.current.set(stockId, updated);
      if (selectedId === stockId) setPriceSeries(updated);
    },
    [selectedId],
  );

  return { priceSeries, chartLoading, handlePriceUpdate };
}
