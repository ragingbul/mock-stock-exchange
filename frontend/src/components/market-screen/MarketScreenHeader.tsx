"use client";

import { fmtPct, signClass } from "@/lib/marketFormat";

type Props = {
  elapsed: string;
  phase: string;
  marketChangePct: string;
};

export function MarketScreenHeader({ elapsed, phase, marketChangePct }: Props) {
  const n = Number(marketChangePct);
  const arrow = n > 0.05 ? "▲" : n < -0.05 ? "▼" : "●";

  return (
    <header className="flex flex-wrap items-end justify-between gap-6 border-b border-white/20 pb-6">
      <div>
        <p className="text-sm uppercase tracking-[0.35em] text-[#22c55e]">TRADEVERSE</p>
        <h1 className="mt-2 text-4xl font-bold tracking-wide md:text-5xl">LIVE MARKET</h1>
      </div>
      <div className="text-right">
        <p className="font-mono text-4xl tabular-nums md:text-5xl">{elapsed}</p>
        <p className="mt-1 text-lg uppercase tracking-wider text-white/70">{phase.replace(/^PHASE \d+ — /, "")}</p>
      </div>
      <div className="w-full text-center md:w-auto md:text-right">
        <p className="text-sm uppercase tracking-widest text-white/50">Market</p>
        <p className={`font-mono text-3xl tabular-nums md:text-4xl ${signClass(marketChangePct)}`}>
          {arrow} {fmtPct(marketChangePct)}
        </p>
      </div>
    </header>
  );
}
