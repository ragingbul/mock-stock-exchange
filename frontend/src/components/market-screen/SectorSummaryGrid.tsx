"use client";

import type { SectorGroup } from "@/components/StockSidebar";
import { fmtPct, signClass } from "@/lib/marketFormat";

type Props = {
  sectors: SectorGroup[];
};

export function SectorSummaryGrid({ sectors }: Props) {
  return (
    <section className="border border-white/15 p-4">
      <p className="mb-3 text-xs uppercase tracking-widest text-white/40">Sector summary</p>
      <div className="grid grid-cols-2 gap-x-8 gap-y-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {sectors.map((s) => (
          <div key={s.slug} className="flex items-baseline justify-between gap-2 font-mono text-sm md:text-base">
            <span className="truncate uppercase text-white/70">{s.name}</span>
            <span className={`tabular-nums ${signClass(s.sector_change_pct)}`}>{fmtPct(s.sector_change_pct)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
