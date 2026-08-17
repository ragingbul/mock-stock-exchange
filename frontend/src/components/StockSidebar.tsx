"use client";

import { useMemo, useState } from "react";
import { fmtMoney, fmtPct, signClass } from "@/lib/marketFormat";

export type SidebarStock = {
  id: number;
  ticker: string;
  company_name: string;
  last_traded_price: string;
  percent_change: string | null;
  sector_name?: string | null;
};

export type SectorStockRow = {
  stock_id: number;
  ticker: string;
  company_name: string;
  last_traded_price: string;
  percent_change: string;
};

export type SectorGroup = {
  sector_id: number;
  slug: string;
  name: string;
  stock_count: number;
  sector_change_pct: string;
  stocks: SectorStockRow[];
};

type Props = {
  sectors: SectorGroup[];
  selectedId: number | null;
  onSelect: (id: number) => void;
};

export function StockSidebar({ sectors, selectedId, onSelect }: Props) {
  const sectorKeys = useMemo(() => sectors.map((s) => s.slug), [sectors]);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());

  const expanded = useMemo(() => {
    const next = new Set(sectorKeys);
    for (const key of collapsed) next.delete(key);
    return next;
  }, [sectorKeys, collapsed]);

  function toggleSector(slug: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  return (
    <aside className="flex h-full flex-col border border-white/15 bg-black">
      <p className="border-b border-white/10 px-3 py-2 text-[10px] uppercase tracking-wider text-white/40">
        Stocks
      </p>
      <div className="flex-1 overflow-y-auto">
        {sectors.map((sector) => {
          const isOpen = expanded.has(sector.slug);
          const avg = sector.sector_change_pct;
          return (
            <div key={sector.slug} className="border-b border-white/5">
              <button
                type="button"
                onClick={() => toggleSector(sector.slug)}
                className="sticky top-0 z-10 flex w-full items-center justify-between bg-black/95 px-3 py-2 text-left hover:bg-white/5"
              >
                <span className="text-[10px] uppercase tracking-wide text-white/50">
                  {isOpen ? "▼" : "▶"} {sector.name}
                </span>
                <span className={`text-[10px] tabular-nums ${signClass(avg)}`}>
                  Avg {fmtPct(avg)}
                </span>
              </button>
              {isOpen && (
                <ul>
                  {sector.stocks.map((s) => (
                    <li key={s.stock_id}>
                      <button
                        type="button"
                        onClick={() => onSelect(s.stock_id)}
                        className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-white/5 ${
                          selectedId === s.stock_id ? "bg-white/10" : ""
                        }`}
                      >
                        <span>
                          <span className="block font-medium">{s.ticker}</span>
                          <span className="block text-[10px] text-white/40">{s.company_name}</span>
                        </span>
                        <span className="text-right">
                          <span className="block tabular-nums">{fmtMoney(s.last_traded_price)}</span>
                          <span className={`block text-[10px] ${signClass(s.percent_change)}`}>
                            {fmtPct(s.percent_change)}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                  {!sector.stocks.length && (
                    <li className="px-3 py-2 text-[10px] text-white/30">No active stocks</li>
                  )}
                </ul>
              )}
            </div>
          );
        })}
        {!sectors.length && <p className="p-3 text-xs text-white/30">Loading stocks…</p>}
      </div>
    </aside>
  );
}
