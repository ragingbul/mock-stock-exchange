"use client";

import { signClass } from "@/lib/marketFormat";

export type NewsItem = {
  id: number;
  title: string;
  description: string;
  effective_impact?: string;
  released_at?: string;
};

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
          {selectedNews.released_at && (
            <p className="mt-2 text-white/40">
              {new Date(selectedNews.released_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-2">
        <ul className="space-y-2 text-xs">
          {news.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className="w-full p-1 text-left hover:bg-white/5"
                onClick={() => onSelectNews(n)}
              >
                <span className={signClass(n.effective_impact)}>
                  ●{" "}
                  {n.released_at
                    ? new Date(n.released_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                    : "—"}
                </span>
                <p className="mt-0.5 line-clamp-2">{n.title}</p>
              </button>
            </li>
          ))}
          {!news.length && <li className="p-1 text-white/30">No news yet</li>}
        </ul>
      </div>
    </aside>
  );
}
