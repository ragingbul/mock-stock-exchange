"use client";

import { useCallback, useEffect, useState } from "react";
import { CurrentEventPanel } from "@/components/market-screen/CurrentEventPanel";
import { MarketScreenHeader } from "@/components/market-screen/MarketScreenHeader";
import { SectorImpactMatrix } from "@/components/market-screen/SectorImpactMatrix";
import { SectorSummaryGrid } from "@/components/market-screen/SectorSummaryGrid";
import type { SectorGroup } from "@/components/StockSidebar";
import { useMarketWebSocket } from "@/hooks/useMarketWebSocket";
import { apiGet } from "@/lib/api";
import type { NewsImpactRow } from "@/lib/sectorImpactUtils";

type MarketStatus = {
  elapsed: string;
  current_phase: string;
  status: string;
  market_change_pct: string;
  latest_news: {
    id: number;
    title: string;
    description: string;
    released_at: string | null;
    sector_impacts: Record<string, number>;
  } | null;
};

type NewsItem = NewsImpactRow & {
  description?: string;
  released_at?: string;
};

export default function MarketScreenPage() {
  const [status, setStatus] = useState<MarketStatus | null>(null);
  const [sectors, setSectors] = useState<SectorGroup[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);

  const refresh = useCallback(async () => {
    const [st, sec, nw] = await Promise.all([
      apiGet<MarketStatus>("/market/status"),
      apiGet<SectorGroup[]>("/market/sectors"),
      apiGet<NewsItem[]>("/news"),
    ]);
    setStatus(st);
    setSectors(sec);
    setNews(nw);
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 5000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useMarketWebSocket({
    onMessage: (msg) => {
      if (
        msg.event === "NEWS_RELEASED" ||
        msg.event === "PRICE_UPDATED" ||
        msg.event === "TRADE_EXECUTED" ||
        msg.event === "SIMULATION_STATUS" ||
        msg.event === "SIMULATION_CLOCK"
      ) {
        refresh();
      }
    },
  });

  const latest = status?.latest_news;

  return (
    <div className="min-h-screen bg-black p-4 font-mono text-white md:p-8">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6">
        <MarketScreenHeader
          elapsed={status?.elapsed ?? "00:00:00"}
          phase={status?.current_phase ?? "—"}
          marketChangePct={status?.market_change_pct ?? "0"}
        />

        {latest && (
          <CurrentEventPanel
            title={latest.title}
            description={latest.description}
            sectorImpacts={latest.sector_impacts}
          />
        )}

        <SectorSummaryGrid sectors={sectors} />

        <SectorImpactMatrix news={news} />
      </div>
    </div>
  );
}
