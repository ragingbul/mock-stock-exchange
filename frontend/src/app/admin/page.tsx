"use client";

import { useCallback, useEffect, useState } from "react";
import { NewsPanel, type NewsItem } from "@/components/NewsPanel";
import { useMarketWebSocket } from "@/hooks/useMarketWebSocket";
import { adminGet, adminLogin, adminPost } from "@/lib/api";

type SimStatus = {
  status: string;
  elapsed: string;
  duration: string;
  elapsed_sec: number;
  current_phase: string;
  current_event?: { headline: string; checkpoint_id?: number } | null;
  next_event?: { headline: string } | null;
  seconds_to_next_event?: number | null;
  completed_checkpoint_count: number;
  total_checkpoint_count: number;
  checkpoints?: Array<{
    checkpoint_id: number;
    headline: string;
    status: string;
    timestamp: string;
    type: string;
  }>;
};

function fmtCountdown(sec: number | null | undefined) {
  if (sec == null) return "—";
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

export default function AdminPage() {
  const [status, setStatus] = useState<SimStatus | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [adminToken, setAdminToken] = useState<string | null>(null);
  const [secret, setSecret] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setAdminToken(window.localStorage.getItem("mse_admin_token"));
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    if (!adminToken) return;
    try {
      const data = await adminGet<SimStatus>("/admin/simulation/status");
      setStatus(data);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to load status");
    }
  }, [adminToken]);

  const refreshNews = useCallback(async () => {
    if (!adminToken) return;
    try {
      const data = await adminGet<NewsItem[]>("/admin/news");
      setNews(data);
    } catch {
      /* non-fatal */
    }
  }, [adminToken]);

  useEffect(() => {
    if (!adminToken) return;
    refreshStatus();
    refreshNews();
    const id = setInterval(() => {
      refreshStatus();
      refreshNews();
    }, 2000);
    return () => clearInterval(id);
  }, [refreshStatus, refreshNews, adminToken]);

  useMarketWebSocket({
    onMessage: (msg) => {
      if (msg.event === "NEWS_RELEASED") {
        refreshNews();
      }
    },
  });

  async function act(action: "start" | "stop" | "reset") {
    if (!adminToken) return;
    setBusy(true);
    setMsg("");
    try {
      await adminPost(`/admin/simulation/${action}`);
      setMsg(`${action.toUpperCase()} OK`);
      await refreshStatus();
      if (action === "reset") {
        setNews([]);
        setSelectedNews(null);
        await refreshNews();
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy(false);
    }
  }

  const cp = status?.checkpoints ?? [];
  const currentId = status?.current_event?.checkpoint_id;

  if (!adminToken) {
    return (
      <main className="min-h-screen bg-black text-white p-8 max-w-md mx-auto font-mono flex flex-col justify-center gap-4">
        <h1 className="text-2xl font-bold tracking-widest text-center">TRADEVERSE ADMIN</h1>
        <input
          type="password"
          placeholder="Admin secret"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          className="bg-neutral-900 border border-neutral-700 rounded px-3 py-2"
        />
        <button
          className="px-4 py-2 bg-green-700 rounded"
          onClick={async () => {
            try {
              const res = await adminLogin(secret);
              setAdminToken(res.access_token);
              setMsg("Authenticated");
            } catch (e) {
              setMsg(e instanceof Error ? e.message : "Login failed");
            }
          }}
        >
          Login
        </button>
        {msg && <p className="text-sm text-yellow-300 text-center">{msg}</p>}
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-black text-white p-8 max-w-2xl mx-auto font-mono">
      <h1 className="text-2xl font-bold tracking-widest mb-8 text-center">TRADEVERSE ADMIN</h1>

      <div className="flex gap-4 justify-center mb-8">
        <button
          disabled={busy}
          onClick={() => act("start")}
          className="px-8 py-3 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded"
        >
          ▶ START
        </button>
        <button
          disabled={busy}
          onClick={() => act("stop")}
          className="px-8 py-3 bg-yellow-700 hover:bg-yellow-600 disabled:opacity-50 rounded"
        >
          ⏸ STOP
        </button>
        <button
          disabled={busy}
          onClick={() => act("reset")}
          className="px-8 py-3 bg-red-800 hover:bg-red-700 disabled:opacity-50 rounded"
        >
          ↻ RESET
        </button>
      </div>

      {msg && <p className="text-center text-sm text-yellow-300 mb-4">{msg}</p>}

      {status && (
        <section className="border border-neutral-700 rounded p-4 space-y-3 mb-6">
          <p className="text-xl text-center">
            {status.elapsed} / {status.duration}
          </p>
          <p className="text-center text-neutral-300">{status.current_phase}</p>
          <p>
            <span className="text-neutral-500">CURRENT: </span>
            {status.current_event?.headline ?? "—"}
          </p>
          <p>
            <span className="text-neutral-500">NEXT: </span>
            {status.next_event?.headline ?? "—"}
          </p>
          <p>
            <span className="text-neutral-500">IN: </span>
            {fmtCountdown(status.seconds_to_next_event)}
          </p>
          <p className="text-sm text-neutral-400">
            Checkpoints {status.completed_checkpoint_count}/{status.total_checkpoint_count} · Status: {status.status}
          </p>
        </section>
      )}

      <section className="border border-neutral-700 rounded p-4 max-h-96 overflow-y-auto mb-6">
        <h2 className="text-sm text-neutral-500 mb-3">CHECKPOINTS (read-only)</h2>
        <ul className="space-y-1 text-sm">
          {cp.map((c) => {
            const mark =
              c.status === "executed"
                ? currentId === c.checkpoint_id
                  ? "●"
                  : "✓"
                : "○";
            return (
              <li key={c.checkpoint_id} className={c.status === "executed" ? "text-green-400" : "text-neutral-500"}>
                {mark} {c.timestamp} {c.headline}
              </li>
            );
          })}
        </ul>
      </section>

      <NewsPanel news={news} selectedNews={selectedNews} onSelectNews={setSelectedNews} />

      <p className="text-center text-xs text-neutral-600 mt-8">
        Simulation runs on the server. Closing this tab does not stop the movie.
      </p>
    </main>
  );
}
