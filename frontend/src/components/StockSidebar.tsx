"use client";

export type SidebarStock = {
  id: number;
  ticker: string;
  company_name: string;
  last_traded_price: string;
  percent_change: string | null;
  sector_name?: string | null;
};

function num(v: string | number | null | undefined): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function signClass(v: string | number | null | undefined): string {
  const n = num(v);
  if (n > 0) return "text-[#22c55e]";
  if (n < 0) return "text-[#ef4444]";
  return "text-white/70";
}

function fmtPct(v: string | null | undefined): string {
  const n = num(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

type Props = {
  stocks: SidebarStock[];
  selectedId: number | null;
  onSelect: (id: number) => void;
};

export function StockSidebar({ stocks, selectedId, onSelect }: Props) {
  const groups = new Map<string, SidebarStock[]>();
  for (const s of stocks) {
    const key = s.sector_name || "Other";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(s);
  }

  return (
    <aside className="flex h-full flex-col border border-white/15 bg-black">
      <p className="border-b border-white/10 px-3 py-2 text-[10px] uppercase tracking-wider text-white/40">
        Stocks
      </p>
      <div className="flex-1 overflow-y-auto">
        {[...groups.entries()].map(([sector, list]) => (
          <div key={sector} className="border-b border-white/5">
            <p className="sticky top-0 bg-black/95 px-3 py-1 text-[10px] uppercase text-white/35">
              {sector}
            </p>
            <ul>
              {list.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(s.id)}
                    className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-white/5 ${
                      selectedId === s.id ? "bg-white/10" : ""
                    }`}
                  >
                    <span className="font-medium">{s.ticker}</span>
                    <span className="text-right">
                      <span className="block tabular-nums">₹{num(s.last_traded_price).toFixed(2)}</span>
                      <span className={`block text-[10px] ${signClass(s.percent_change)}`}>
                        {fmtPct(s.percent_change)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </aside>
  );
}
