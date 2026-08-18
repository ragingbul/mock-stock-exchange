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
  selectedNews: NewsItem | null;
  onSelectNews: (item: NewsItem) => void;
};

/** Full released-news list for admin monitoring. */
export function NewsPanel({ news, selectedNews, onSelectNews }: Props) {
  return (
    <section className="flex max-h-96 flex-col border border-neutral-700 rounded overflow-hidden">
      <p className="border-b border-neutral-700 px-3 py-2 text-sm text-neutral-500">RELEASED NEWS</p>

      {selectedNews && (
        <div className="border-b border-neutral-700 p-3 text-xs">
          <p className="text-neutral-500">Detail</p>
          <p className="mt-1 font-medium">{selectedNews.title}</p>
          <p className="mt-1 text-neutral-400">{selectedNews.description}</p>
          {selectedNews.released_at && (
            <p className="mt-2 text-neutral-500">
              {new Date(selectedNews.released_at).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          )}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-2">
        <ul className="space-y-2 text-sm">
          {news.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className="w-full rounded p-1 text-left hover:bg-neutral-900"
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
          {!news.length && <li className="p-1 text-neutral-600">No news released yet</li>}
        </ul>
      </div>
    </section>
  );
}
