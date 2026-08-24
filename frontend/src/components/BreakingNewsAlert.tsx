"use client";

import type { NewsItem } from "@/components/NewsPanel";

type Props = {
  news: NewsItem | null;
  onDismiss: () => void;
};

/** Single breaking-news alert — headline only. */
export function BreakingNewsAlert({ news, onDismiss }: Props) {
  if (!news) return null;

  return (
    <div className="fixed inset-x-4 top-20 z-40 mx-auto max-w-lg border border-[#ef4444]/50 bg-black p-4 shadow-lg md:inset-x-auto md:right-6 md:top-24">
      <p className="text-[10px] font-bold uppercase tracking-wider text-[#ef4444]">Breaking news</p>
      <p className="mt-2 text-base font-medium leading-snug">{news.title}</p>
      <button
        type="button"
        className="mt-3 text-xs text-white/50 underline"
        onClick={onDismiss}
      >
        Dismiss
      </button>
    </div>
  );
}
