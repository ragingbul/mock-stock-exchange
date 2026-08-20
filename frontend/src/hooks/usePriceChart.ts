"use client";

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import { apiGet } from "@/lib/api";
import { num } from "@/lib/marketFormat";

export type PricePoint = { t: string; px: number; i: number };

const MAX_POINTS = 900;
const REFETCH_INTERVAL_MS = 30_000;

type TradeRow = { id: number; price: string; executed_at?: string };

function tradesToSeries(trades: TradeRow[]): PricePoint[] {
  const sorted = [...trades].sort((a, b) =>
    String(a.executed_at ?? a.id).localeCompare(String(b.executed_at ?? b.id)),
  );
  return sorted.map((tr, idx) => ({
    t: tr.executed_at
      ? new Date(tr.executed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : `#${tr.id}`,
    px: num(tr.price),
    i: idx,
  }));
}

function appendPoint(
  stockId: number,
  series: PricePoint[],
  px: number,
  seqRef: MutableRefObject<Map<number, number>>,
): PricePoint[] {
  const last = series[series.length - 1];
  if (last && last.px === px) return series;

  const nextSeq = (seqRef.current.get(stockId) ?? series.length - 1) + 1;
  seqRef.current.set(stockId, nextSeq);
  const t = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const next = [...series, { t, px, i: nextSeq }];
  if (next.length > MAX_POINTS) return next.slice(next.length - MAX_POINTS);
  return next;
}

export type PriceUpdatePayload = {
  stock_id?: number;
  ltp?: string;
  trades?: Array<{ price: string }>;
};

export type MarketPulseStock = {
  stock_id: number;
  ltp: string;
  ticker?: string;
  percent_change?: string;
};

export function usePriceChart(selectedId: number | null, fallbackPrice?: string) {
  const cacheRef = useRef<Map<number, PricePoint[]>>(new Map());
  const seqRef = useRef<Map<number, number>>(new Map());
  const lastFetchRef = useRef<Map<number, number>>(new Map());
  const fallbackRef = useRef(fallbackPrice);
  const selectedIdRef = useRef(selectedId);
  const [priceSeries, setPriceSeries] = useState<PricePoint[]>([]);
  const [chartLoading, setChartLoading] = useState(false);

  useEffect(() => {
    fallbackRef.current = fallbackPrice;
  }, [fallbackPrice]);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  const loadHistory = useCallback(async (stockId: number, force = false) => {
    const now = Date.now();
    const liveCached = cacheRef.current.get(stockId) ?? [];
    const lastFetch = lastFetchRef.current.get(stockId) ?? 0;

    if (liveCached.length > 0) {
      setPriceSeries(liveCached);
      if (!force && liveCached.length > 1) return;
      if (!force && now - lastFetch < REFETCH_INTERVAL_MS) return;
    }

    setChartLoading(liveCached.length === 0);
    try {
      const trades = await apiGet<TradeRow[]>(`/trades?stock_id=${stockId}&limit=${MAX_POINTS}`);
      const freshCached = cacheRef.current.get(stockId) ?? [];
      if (freshCached.length > 1) {
        setPriceSeries(freshCached);
        return;
      }

      const fromTrades = trades.length > 0 ? tradesToSeries(trades) : [];
      let series: PricePoint[];
      if (freshCached.length >= fromTrades.length && freshCached.length > 0) {
        series = freshCached;
      } else if (fromTrades.length > 0) {
        series = fromTrades;
        seqRef.current.set(stockId, fromTrades.length - 1);
      } else if (freshCached.length > 0) {
        series = freshCached;
      } else if (fallbackRef.current) {
        series = [{ t: "now", px: num(fallbackRef.current), i: 0 }];
        seqRef.current.set(stockId, 0);
      } else {
        series = [];
      }

      cacheRef.current.set(stockId, series);
      lastFetchRef.current.set(stockId, now);
      setPriceSeries(series);
    } finally {
      setChartLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    void loadHistory(selectedId);
  }, [selectedId, loadHistory]);

  const applyPrice = useCallback((stockId: number, px: number) => {
    const cached = cacheRef.current.get(stockId) ?? [];
    const base = cached.length > 0 ? cached : [{ t: "now", px, i: 0 }];
    if (cached.length === 0) seqRef.current.set(stockId, 0);
    const updated = appendPoint(stockId, base, px, seqRef);
    cacheRef.current.set(stockId, updated);
    return updated;
  }, []);

  const handlePriceUpdate = useCallback(
    (payload: PriceUpdatePayload) => {
      const stockId = payload.stock_id;
      if (!stockId) return;

      let px: number | null = null;
      if (payload.ltp) px = num(payload.ltp);
      else if (payload.trades?.length) px = num(payload.trades[payload.trades.length - 1].price);
      if (px === null) return;

      const updated = applyPrice(stockId, px);
      if (selectedIdRef.current === stockId) setPriceSeries(updated);
    },
    [applyPrice],
  );

  const handleMarketPulse = useCallback(
    (stocks: MarketPulseStock[]) => {
      if (!stocks.length) return;
      let selectedUpdated: PricePoint[] | null = null;
      for (const row of stocks) {
        const updated = applyPrice(row.stock_id, num(row.ltp));
        if (selectedIdRef.current === row.stock_id) selectedUpdated = updated;
      }
      if (selectedUpdated) setPriceSeries(selectedUpdated);
    },
    [applyPrice],
  );

  return { priceSeries, chartLoading, handlePriceUpdate, handleMarketPulse };
}
