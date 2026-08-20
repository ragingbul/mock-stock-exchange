"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

function mergeStatus(prev: SimStatus | null, next: Partial<SimStatus>): SimStatus {
  const checkpoints =
    next.checkpoints && next.checkpoints.length > 0
      ? next.checkpoints
      : prev?.checkpoints ?? [];
  return { ...(prev ?? (next as SimStatus)), ...next, checkpoints };
}

export default function AdminPage() {
  const [status, setStatus] = useState<SimStatus | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [adminToken, setAdminToken] = useState<string | null>(null);
  const [secret, setSecret] = useState("");
  const statusInflight = useRef(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setAdminToken(window.localStorage.getItem("mse_admin_token"));
    }
  }, []);

  const refreshStatus = useCallback(
    async (opts?: { includeCheckpoints?: boolean; quiet?: boolean }) => {
      if (!adminToken || statusInflight.current) return;
      statusInflight.current = true;
      try {
        const data = await adminGet<SimStatus>("/admin/simulation/status", {
          include_checkpoints: opts?.includeCheckpoints ?? false,
        });
        setStatus((prev) => mergeStatus(prev, data));
        if (!opts?.quiet) setMsg("");
      } catch (e) {
        if (!opts?.quiet) {
          setMsg(e instanceof Error ? e.message : "Failed to load status");
        }
      } finally {
        statusInflight.current = false;
      }
    },
    [adminToken],
  );

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
    refreshStatus({ includeCheckpoints: true });
    refreshNews();
    const id = setInterval(() => {
      refreshStatus({ includeCheckpoints: false, quiet: true });
    }, 8000);
    return () => clearInterval(id);
  }, [refreshStatus, refreshNews, adminToken]);

  useMarketWebSocket({
    onMessage: (msg) => {
      if (msg.event === "NEWS_RELEASED") {
        refreshNews();
      }
      if (msg.event === "SIMULATION_CLOCK" || msg.event === "SIMULATION_STATUS") {
        const payload = (msg.payload ?? msg) as Partial<SimStatus>;
        setStatus((prev) => mergeStatus(prev, payload));
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
      await refreshStatus({ includeCheckpoints: true });
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
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 bg-black p-4 font-mono text-white sm:p-8">
        <h1 className="text-center text-xl font-bold tracking-widest sm:text-2xl">TRADEVERSE ADMIN</h1>
        <input
          type="password"
          placeholder="Admin secret"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          className="rounded border border-neutral-700 bg-neutral-900 px-3 py-3"
        />
        <button
          className="rounded bg-green-700 px-4 py-3"
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
        {msg && <p className="text-center text-sm text-yellow-300">{msg}</p>}
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen max-w-2xl bg-black p-4 font-mono text-white sm:p-8">
      <header className="sticky top-0 z-20 -mx-4 mb-6 border-b border-white/10 bg-black/95 px-4 py-3 backdrop-blur sm:-mx-8 sm:px-8">
        <h1 className="text-center text-lg font-bold tracking-widest sm:text-2xl">TRADEVERSE ADMIN</h1>
        <div className="mt-3 grid grid-cols-3 gap-2 sm:gap-4">
          <button
            disabled={busy}
            onClick={() => act("start")}
            className="bg-green-700 px-2 py-3 text-xs hover:bg-green-600 disabled:opacity-50 sm:px-4 sm:text-sm"
          >
            ▶ START
          </button>
          <button
            disabled={busy}
            onClick={() => act("stop")}
            className="bg-yellow-700 px-2 py-3 text-xs hover:bg-yellow-600 disabled:opacity-50 sm:px-4 sm:text-sm"
          >
            ⏸ STOP
          </button>
          <button
            disabled={busy}
            onClick={() => act("reset")}
            className="bg-red-800 px-2 py-3 text-xs hover:bg-red-700 disabled:opacity-50 sm:px-4 sm:text-sm"
          >
            ↻ RESET
          </button>
        </div>
        {msg && <p className="mt-2 text-center text-sm text-yellow-300">{msg}</p>}
      </header>

      {status && (
        <section className="mb-6 space-y-3 border border-neutral-700 p-4">
          <p className="text-center text-lg sm:text-xl">
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
            Checkpoints {status.completed_checkpoint_count}/{status.total_checkpoint_count} · Status:{" "}
            {status.status}
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
