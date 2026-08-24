"use client";

import { useState } from "react";
import type { NewsItem } from "@/components/NewsPanel";

type Props = {
  newsFeed: NewsItem[];
  selected: NewsItem | null;
  onSelect: (item: NewsItem) => void;
};

/** Latest news strip with dropdown history and expandable brief bullets. */
export function LatestNewsPanel({ newsFeed, selected, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const active = selected ?? newsFeed[0];
  if (!active) return null;

  const briefs = active.brief_points?.length
    ? active.brief_points
    : active.description
      ? [active.description]
      : [];

  return (
    <div className="border-b border-[#ef4444]/40 bg-[#ef4444]/10 px-3 py-2 sm:px-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] uppercase tracking-wider text-[#ef4444]">Latest news</p>
        {newsFeed.length > 1 && (
          <button
            type="button"
            className="text-[10px] uppercase text-white/50 hover:text-white"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "Hide" : "History"} ({newsFeed.length})
          </button>
        )}
      </div>

      <p className="mt-1 text-sm font-medium leading-snug">{active.title}</p>

      {briefs.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-white/70">
          {briefs.map((point, i) => (
            <li key={i} className="flex gap-2 leading-snug">
              <span className="text-[#ef4444]">•</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}

      {open && newsFeed.length > 1 && (
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
                  onClick={() => {
                    onSelect(item);
                    setOpen(false);
                  }}
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
