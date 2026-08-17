"use client";

export type NewsItem = {
  id: number;
  title: string;
  description: string;
  effective_impact?: string;
  released_at?: string;
  sector_impacts?: Record<string, number>;
};

function num(v: string | number | null | undefined): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function signClass(v: string | number | null | undefined): string {
  const n = num(v);
  if (n > 0) return "text-[#22c55e]";
  if (n < 0) return "text-[#ef4444]";
  return "text-white/60";
}

type Props = {
  news: NewsItem[];
  breaking: NewsItem | null;
  onDismissBreaking: () => void;
  onSelectNews: (item: NewsItem) => void;
  selectedNews: NewsItem | null;
};

export function NewsPanel({ news, breaking, onDismissBreaking, onSelectNews, selectedNews }: Props) {
  return (
    <aside className="flex h-full flex-col border border-white/15 bg-black">
      <p className="border-b border-white/10 px-3 py-2 text-[10px] uppercase tracking-wider text-white/40">
        News
      </p>

      {breaking && (
        <div className="border-b border-[#ef4444]/40 bg-[#ef4444]/10 p-3">
          <p className="text-[10px] font-bold text-[#ef4444]">BREAKING NEWS</p>
          <p className="mt-1 text-sm">{breaking.title}</p>
          <p className="mt-1 text-xs text-white/60">{breaking.description}</p>
          <button
            type="button"
            className="mt-2 text-[10px] text-white/50 underline"
            onClick={onDismissBreaking}
          >
            Dismiss
          </button>
        </div>
      )}

      {selectedNews && (
        <div className="border-b border-white/10 p-3 text-xs">
          <p className="text-white/40">Detail</p>
          <p className="mt-1 font-medium">{selectedNews.title}</p>
          <p className="mt-1 text-white/60">{selectedNews.description}</p>
          {selectedNews.sector_impacts && (
            <ul className="mt-2 space-y-0.5">
              {Object.entries(selectedNews.sector_impacts).map(([k, v]) => (
                <li key={k} className={v >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}>
                  {k} {v > 0 ? "+" : ""}
                  {v}%
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-2">
        <ul className="space-y-2 text-xs">
          {news.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className="w-full text-left hover:bg-white/5 p-1"
                onClick={() => onSelectNews(n)}
              >
                <span className={signClass(n.effective_impact)}>
                  {num(n.effective_impact) >= 0 ? "🟢" : "🔴"}{" "}
                  {n.released_at
                    ? new Date(n.released_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                    : "—"}
                </span>
                <p className="mt-0.5 line-clamp-2">{n.title}</p>
              </button>
            </li>
          ))}
          {!news.length && <li className="text-white/30 p-1">No news yet</li>}
        </ul>
      </div>
    </aside>
  );
}
