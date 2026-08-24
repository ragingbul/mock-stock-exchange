"use client";

import { useEffect, useState } from "react";
import type { NewsItem } from "@/components/NewsPanel";

type Props = {
  newsFeed: NewsItem[];
  selected: NewsItem | null;
  onSelect: (item: NewsItem) => void;
};

/** Latest news strip — headline by default; brief and history in separate dropdowns. */
export function LatestNewsPanel({ newsFeed, selected, onSelect }: Props) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const active = selected ?? newsFeed[0];

  useEffect(() => {
    if (active) setBriefOpen(false);
  }, [active?.id]);

  if (!active) return null;

  const briefs = active.brief_points?.length
    ? active.brief_points
    : active.description
      ? [active.description]
      : [];

  function selectItem(item: NewsItem) {
    onSelect(item);
    setHistoryOpen(false);
    setBriefOpen(false);
  }

  return (
    <div className="border-b border-[#ef4444]/40 bg-[#ef4444]/10 px-3 py-2 sm:px-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] uppercase tracking-wider text-[#ef4444]">Latest news</p>
        <div className="flex items-center gap-2">
          {briefs.length > 0 && (
            <button
              type="button"
              className="text-[10px] uppercase text-white/50 hover:text-white"
              onClick={() => setBriefOpen((v) => !v)}
            >
              {briefOpen ? "Hide brief" : "Brief"}
            </button>
          )}
          {newsFeed.length > 1 && (
            <button
              type="button"
              className="text-[10px] uppercase text-white/50 hover:text-white"
              onClick={() => setHistoryOpen((v) => !v)}
            >
              {historyOpen ? "Hide history" : `History (${newsFeed.length})`}
            </button>
          )}
        </div>
      </div>

      <p className="mt-1 text-sm font-medium leading-snug">{active.title}</p>

      {briefOpen && briefs.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-[#ef4444]/20 pt-2 text-xs text-white/70">
          {briefs.map((point, i) => (
            <li key={i} className="flex gap-2 leading-snug">
              <span className="shrink-0 text-[#ef4444]">•</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}

      {historyOpen && newsFeed.length > 1 && (
        <div className="mt-3 border-t border-[#ef4444]/20 pt-2">
          <p className="text-[10px] uppercase text-white/40">Earlier news</p>
          <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto">
            {newsFeed.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={`w-full rounded px-1 py-1 text-left text-xs hover:bg-white/5 ${
                    item.id === active.id ? "text-white" : "text-white/60"
                  }`}
                  onClick={() => selectItem(item)}
                >
                  <span className="text-white/40">
                    {item.released_at
                      ? new Date(item.released_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—"}{" "}
                  </span>
                  {item.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
