import type { SectorGroup } from "@/components/StockSidebar";
import type { LeaderboardRow } from "@/components/Leaderboard";

const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX ?? "/api/v1";
const REQUEST_TIMEOUT_MS = 30_000;

function defaultHeaders(): HeadersInit {
  const headers: Record<string, string> = {};
  if (typeof window !== "undefined" && window.location.hostname.endsWith(".ngrok-free.dev")) {
    headers["ngrok-skip-browser-warning"] = "1";
  }
  return headers;
}

function isProductionBuild(): boolean {
  return process.env.NODE_ENV === "production";
}

/** Resolve API base URL: env override, same-origin in prod browser, else dev fallback. */
export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (envUrl) return envUrl;
  if (isProductionBuild()) {
    if (typeof window !== "undefined") {
      return window.location.origin;
    }
    return "http://localhost";
  }
  if (typeof window !== "undefined") {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl()}${API_PREFIX}${normalized}`;
}

export function wsUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL?.replace(/\/$/, "");
  const base =
    explicit ??
    getApiBaseUrl().replace(/^https:/, "wss:").replace(/^http:/, "ws:");
  const path = `${base}${API_PREFIX}/ws`;
  if (typeof window === "undefined") return path;
  const token = window.localStorage.getItem("mse_access_token");
  if (!token) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}token=${encodeURIComponent(token)}`;
}

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("mse_access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchWithTimeout(
  input: string,
  init?: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, {
      ...init,
      headers: { ...defaultHeaders(), ...authHeaders(), ...(init?.headers ?? {}) },
      signal: controller.signal,
    });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs / 1000}s`);
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

async function parseError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json.detail) return String(json.detail);
  } catch {
    /* use raw text */
  }
  return text || `${res.status} error`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), { cache: "no-store" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function joinSession(displayName: string): Promise<{
  trader_id: number;
  display_name: string;
  access_token: string;
}> {
  const res = await apiPost<{ trader_id: number; display_name: string; access_token: string }>(
    "/auth/join",
    { display_name: displayName },
  );
  if (typeof window !== "undefined") {
    window.localStorage.setItem("mse_access_token", res.access_token);
    window.localStorage.setItem("mse_trader_id", String(res.trader_id));
  }
  return res;
}

export type SessionBootstrap = {
  trader_id: number;
  wallet: Wallet;
  portfolio: Portfolio;
  stocks: SidebarStock[];
  sectors: SectorGroup[];
  simulation: Record<string, unknown>;
  released_news_count?: number;
  released_news?: Array<{ id: number; title: string; description?: string; released_at?: string }>;
  leaderboard?: LeaderboardRow[];
  open_ipos?: IPO[];
  ipo_applications?: Array<{ id: number; ipo_id: number; status: string }>;
};

type Wallet = {
  available_cash: string;
  portfolio_value: string;
  total_pnl: string;
  return_pct: string;
};

type Portfolio = {
  holdings: Array<{ ticker: string | null; quantity: number }>;
};

type SidebarStock = {
  id: number;
  ticker: string;
  company_name?: string;
  last_traded_price?: string;
  ltp?: string;
  percent_change?: string | null;
  is_open?: boolean;
};

type IPO = {
  id: number;
  company_name: string;
  ticker: string;
  issue_price: string;
  lot_size: number;
  maximum_lots_per_user: number;
};

export async function fetchSessionBootstrap(): Promise<SessionBootstrap> {
  return apiGet<SessionBootstrap>("/session/bootstrap");
}

export async function adminLogin(secret: string): Promise<{ access_token: string }> {
  const res = await apiPost<{ access_token: string }>("/auth/admin/login", { secret });
  if (typeof window !== "undefined") {
    window.localStorage.setItem("mse_admin_token", res.access_token);
  }
  return res;
}

export function getAdminAuthHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("mse_admin_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function adminPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetchWithTimeout(apiUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAdminAuthHeaders(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function adminGet<T>(
  path: string,
  params?: Record<string, string | boolean | number>,
): Promise<T> {
  let url = apiUrl(path);
  if (params && Object.keys(params).length > 0) {
    const qs = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      qs.set(key, String(value));
    }
    url = `${url}?${qs.toString()}`;
  }
  const res = await fetchWithTimeout(url, {
    cache: "no-store",
    headers: getAdminAuthHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
